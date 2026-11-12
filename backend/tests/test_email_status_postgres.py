"""Email status against isolated real PostgreSQL and a real (local) SMTP conversation."""

import os
import smtplib
import socketserver
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.core.exceptions import AuthorizationError, ConflictError
from app.core.settings import settings
from app.db import database, schema
from app.db.migrations.access import apply_access_migrations
from app.modules.access.reporting_scope import TrainerPerformanceScope
from app.modules.learning.progress_repository import ProgressRepository
from app.modules.reporting import repository as performance_reporting
from app.services import email_notifications as outbox
from app.services import email_status

pytestmark = pytest.mark.skipif(
    os.getenv("LMS_ACCESS_POSTGRES_TESTS") != "true", reason="isolated PostgreSQL opt-in"
)

_progress = ProgressRepository()
START = datetime(2026, 11, 11, 10, 0, 0)
OWNER = {"trainer_id": "creator"}
OTHER = {"trainer_id": "other"}
SCOPE = TrainerPerformanceScope("creator", all_courses=True)
OTHER_SCOPE = TrainerPerformanceScope("other", all_courses=True)


class _Handler(socketserver.StreamRequestHandler):
    def reply(self, text):
        self.wfile.write(text.encode() + b"\r\n")

    def handle(self):
        behaviour = self.server.behaviours.pop(0) if self.server.behaviours else "accept"
        self.reply("220 fake")
        while line := self.rfile.readline():
            command = line.decode().strip().upper()
            if command.startswith("RCPT") and behaviour == "busy":
                self.reply("421 4.7.0 Too many connections")
            elif command.startswith("RCPT") and behaviour == "no_mailbox":
                self.reply("550 5.1.1 User unknown")
            elif command == "DATA":
                self.reply("354 go")
                body = b""
                while (chunk := self.rfile.readline()) != b".\r\n":
                    body += chunk
                self.server.received.append(body)
                self.reply("250 queued")
            elif command == "QUIT":
                self.reply("500 bad goodbye" if behaviour == "bad_quit" else "221 bye")
                return
            else:
                self.reply("250 ok")


class _FakeMailServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _Handler)
        self.behaviours = []
        self.received = []


@pytest.fixture
def mail(monkeypatch):
    server = _FakeMailServer()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]

    class LocalSmtp(smtplib.SMTP):
        def __init__(self, host, _port, timeout):
            super().__init__("127.0.0.1", port, timeout=timeout)

    monkeypatch.setattr(outbox.smtplib, "SMTP", LocalSmtp)
    monkeypatch.setattr(settings, "email_delivery_mode", "smtp")
    monkeypatch.setattr(settings, "smtp_host", "mail.example.test")
    monkeypatch.setattr(settings, "smtp_port", 25)
    monkeypatch.setattr(settings, "smtp_use_starttls", False)
    monkeypatch.setattr(settings, "smtp_use_ssl", False)
    monkeypatch.setattr(settings, "smtp_allow_insecure_relay", True)
    monkeypatch.setattr(settings, "smtp_username", None)
    monkeypatch.setattr(settings, "smtp_password", None)
    monkeypatch.setattr(settings, "email_from_email", "lms@example.test")
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


class Clock:
    def __init__(self):
        self.now = START

    def __call__(self):
        return self.now

    def advance(self, **delta):
        self.now += timedelta(**delta)


@pytest.fixture
def db(monkeypatch):
    pool = database._pool_instance()
    name = "email_status_test_" + uuid4().hex
    with database.get_connection() as connection:
        assert (
            connection.execute("SELECT current_database() AS name").fetchone()["name"]
            == "lms_performance_demo"
        )
        connection.execute(f'CREATE SCHEMA "{name}"')
        connection.execute(f'SET LOCAL search_path TO "{name}"')
        schema._create_tables(connection.cursor())
        apply_access_migrations(connection)
        connection.commit()

    class ScopedPool:
        @contextmanager
        def connection(self):
            with pool.connection() as raw:
                raw.execute(f'SET LOCAL search_path TO "{name}"')
                yield raw

    clock = Clock()
    monkeypatch.setattr(database, "_pool_instance", lambda: ScopedPool())
    monkeypatch.setattr(outbox, "_now", clock)
    monkeypatch.setattr(email_status, "is_admin_trainer", lambda trainer: False)
    monkeypatch.setattr(settings, "email_delivery_mode", "log")
    monkeypatch.setattr(settings, "email_recipient_allowlist", ())
    monkeypatch.setattr(settings, "email_test_mode", False)
    monkeypatch.setattr(settings, "email_max_attempts", 2)
    monkeypatch.setattr(settings, "email_retry_delay_seconds", 300)
    monkeypatch.setattr(settings, "email_lock_timeout_seconds", 600)
    monkeypatch.setattr(settings, "learning_journeys_enabled", False)
    with database.get_connection() as connection:
        for trainer_id in ("creator", "other"):
            connection.execute(
                "INSERT INTO trainers(trainer_id,name) VALUES (?, ?)", (trainer_id, trainer_id)
            )
        connection.execute(
            "INSERT INTO courses(course_id,trainer_id,course_name,status) "
            "VALUES ('course','creator','AML Training','published')"
        )
        connection.execute(
            "INSERT INTO assignment_rules(course_id,is_active,published_at) "
            "VALUES ('course',TRUE,'2026-11-01T00:00:00')"
        )
        connection.commit()
    try:
        yield clock
    finally:
        monkeypatch.setattr(database, "_pool_instance", lambda: pool)
        with database.get_connection() as connection:
            connection.execute(f'DROP SCHEMA "{name}" CASCADE')
            connection.commit()


def add_employee(employee_id, email="default"):
    address = f"{employee_id}@example.test" if email == "default" else email
    with database.get_connection() as connection:
        connection.execute(
            """INSERT INTO employees(employee_id,name,job_title,department,directory_uuid,email)
            VALUES (?, ?, 'Associate', 'Risk', ?, ?)""",
            (employee_id, employee_id, "uuid-" + employee_id, address),
        )
        connection.commit()


def assign(employee_id, deadline_days=30):
    _progress.save(
        employee_id,
        "course",
        {
            "status": "pending",
            "assigned_at": START.isoformat(),
            "deadline": (START + timedelta(days=deadline_days)).isoformat(),
            "modules": {},
            "attempts": {},
            "last_activity_at": START.isoformat(),
        },
    )


def enrol(employee_id, email="default"):
    add_employee(employee_id, email)
    assign(employee_id)


def report(scope=SCOPE, trainer=OWNER, **kwargs):
    return email_status.course_report(scope, trainer, course_id="course", **kwargs)


def row_for(employee_id, **kwargs):
    return next(r for r in report(**kwargs)["rows"] if r["employee_id"] == employee_id)


def run_round(clock):
    outbox.process_pending_notifications()
    clock.advance(minutes=6)


def test_accepted_email(db, mail):
    enrol("a")
    assert row_for("a")["state"] == "queued"
    run_round(db)
    row = row_for("a")
    assert (row["state"], row["label"], row["attempts"]) == ("accepted", "Sent to mail server", 1)
    assert len(mail.received) == 1


def test_busy_then_accepted(db, mail):
    mail.behaviours[:] = ["busy", "accept"]
    enrol("a")
    run_round(db)
    row = row_for("a")
    assert row["state"] == "retrying"
    assert "code 421" in row["detail"] and "not before" in row["detail"]
    run_round(db)
    row = row_for("a")
    assert (row["state"], row["attempts"]) == ("accepted", 2)
    assert row["detail"] == "Accepted on attempt 2."
    assert len(mail.received) == 1


def test_no_mailbox_until_gave_up(db, mail):
    mail.behaviours[:] = ["no_mailbox", "no_mailbox"]
    enrol("a")
    run_round(db)
    run_round(db)
    run_round(db)
    row = row_for("a")
    assert row["state"] == "gave_up"
    assert row["detail"] == "The mail server says this mailbox doesn't exist."
    assert row["can_resend"] and not row["resend_needs_confirmation"]
    assert mail.received == []


def test_bad_goodbye_after_acceptance_is_one_accepted_email(db, mail):
    mail.behaviours[:] = ["bad_quit"]
    enrol("a")
    run_round(db)
    run_round(db)
    assert row_for("a")["state"] == "accepted"
    assert len(mail.received) == 1


class _Crash(BaseException):
    pass


def test_crash_mid_send_is_unknown_and_never_retried_by_itself(db, mail, monkeypatch):
    enrol("a")
    real_send = outbox._send_notification

    def send_then_crash(notification):
        real_send(notification)
        raise _Crash

    with monkeypatch.context() as patch:
        patch.setattr(outbox, "_send_notification", send_then_crash)
        with pytest.raises(_Crash):
            outbox.process_pending_notifications()
    assert len(mail.received) == 1
    assert row_for("a")["state"] == "in_batch"

    db.advance(minutes=11)
    row = row_for("a")
    assert row["state"] == "unknown"
    assert row["resend_needs_confirmation"]

    run_round(db)
    assert len(mail.received) == 1, "must not retry a possibly delivered email by itself"
    assert row_for("a")["state"] == "unknown"

    with pytest.raises(ConflictError):
        email_status.resend(row["notification_id"], OWNER)
    email_status.resend(row["notification_id"], OWNER, confirm_unknown=True)
    assert row_for("a")["state"] == "queued"
    run_round(db)
    assert row_for("a")["state"] == "accepted"
    assert len(mail.received) == 2


def test_emails_without_a_resend_button_still_retry_after_a_crash(db, mail):
    enrol("a")
    with database.get_connection() as connection:
        connection.execute(
            """INSERT INTO email_notifications(
                notification_id, assignment_id, notification_lifecycle, event_type, occurrence_key,
                recipient_role, recipient_email, subject, body_text, status, attempts,
                next_attempt_at, locked_at, created_at, updated_at
            ) SELECT 'stuck', assignment_id, 1, 'due_soon', 'once', 'employee', 'a@example.test',
                's', 'b', 'sending', 1, ?, ?, ?, ? FROM course_assignments WHERE employee_id = 'a'""",
            (START.isoformat(),) * 4,
        )
        connection.execute(
            """INSERT INTO email_delivery_attempts(
                attempt_id, notification_id, started_at, delivery_mode, recipient_email
            ) VALUES ('x', 'stuck', ?, 'smtp', 'a@example.test')""",
            (START.isoformat(),),
        )
        connection.commit()
    db.advance(minutes=11)
    claimed = [row["notification_id"] for row in outbox._claim_pending_notifications(25)]
    assert "stuck" in claimed


def test_rest_of_a_crashed_batch_is_retried_automatically(db, mail, monkeypatch):
    enrol("a")
    enrol("b")
    with monkeypatch.context() as patch:
        patch.setattr(outbox, "_start_attempt", lambda n: (_ for _ in ()).throw(_Crash()))
        with pytest.raises(_Crash):
            outbox.process_pending_notifications()
    db.advance(minutes=11)
    assert {r["state"] for r in report()["rows"]} == {"queued"}
    run_round(db)
    assert {r["state"] for r in report()["rows"]} == {"accepted"}
    assert len(mail.received) == 2


def test_log_mode_is_never_called_sent(db):
    enrol("a")
    run_round(db)
    row = row_for("a")
    assert (row["state"], row["label"]) == ("logged_only", "Not emailed (log mode)")
    assert report()["accepted_count"] == 0
    assert report()["banners"][0]["kind"] == "log"


def test_email_off_is_recorded(db, monkeypatch):
    monkeypatch.setattr(settings, "email_delivery_mode", "disabled")
    enrol("a")
    row = row_for("a")
    assert row["state"] == "skipped"
    assert row["detail"] == "Email delivery was off when assigned."
    assert report()["banners"] == [
        {"kind": "disabled", "message": "Email delivery is off. Nothing here will be sent."}
    ]


def test_skip_reasons_are_recorded_at_the_time(db, mail, monkeypatch):
    enrol("no_address", email=None)
    monkeypatch.setattr(settings, "email_recipient_allowlist", ("someone@example.test",))
    enrol("blocked")
    monkeypatch.setattr(settings, "email_recipient_allowlist", ())
    # A later directory fix must not rewrite why no email was created back then.
    with database.get_connection() as connection:
        connection.execute("UPDATE employees SET email='x@example.test' WHERE employee_id='no_address'")
        connection.commit()
    assert row_for("no_address")["detail"] == "No email address in the directory when assigned."
    assert row_for("blocked")["detail"] == "Not on the recipient allowlist when assigned."


def test_no_record_gives_no_guessed_reason(db, monkeypatch):
    add_employee("a")
    with database.get_connection() as connection:
        connection.execute(
            """INSERT INTO course_assignments(assignment_id,course_id,employee_id,status,assigned_at,deadline)
            VALUES ('old','course','a','pending',?,?)""",
            (START.isoformat(), (START + timedelta(days=9)).isoformat()),
        )
        connection.commit()
    row = row_for("a")
    assert row["state"] == "no_record"
    assert row["detail"] == "The system has no record of an email for this assignment."


def test_old_sent_rows_are_labelled_as_untracked(db, mail):
    enrol("a")
    with database.get_connection() as connection:
        connection.execute(
            "UPDATE email_notifications SET status='sent', sent_at=? WHERE event_type='assigned'",
            (START.isoformat(),),
        )
        connection.commit()
    assert row_for("a")["state"] == "sent_untracked"


def test_deadline_change_while_queued_still_sends_with_no_false_note(db, mail):
    enrol("a")
    assign("a", deadline_days=45)
    run_round(db)
    row = row_for("a")
    assert row["state"] == "accepted"
    assert row["note"] is None
    assert len(mail.received) == 1


def test_deadline_change_after_sending_adds_a_note(db, mail):
    enrol("a")
    run_round(db)
    assign("a", deadline_days=45)
    row = row_for("a")
    assert row["state"] == "accepted"
    assert "No new assignment email was sent" in row["note"]


def test_withdrawn_assignment_records_why_it_was_cancelled(db, mail):
    enrol("a")
    current = _progress.get_for_employee("a")["course"]
    current.update(revoked_at=START.isoformat(), revoked_reason="test", status="revoked")
    _progress.save("a", "course", current)
    run_round(db)
    with database.get_connection() as connection:
        reason = connection.execute(
            "SELECT status, cancel_reason FROM email_notifications WHERE event_type='assigned'"
        ).fetchone()
    assert (reason["status"], reason["cancel_reason"]) == ("cancelled", "assignment_withdrawn")
    assert mail.received == []


def gave_up(db, mail, employee="a"):
    mail.behaviours[:] = ["no_mailbox", "no_mailbox"]
    enrol(employee)
    run_round(db)
    run_round(db)
    return row_for(employee)


def test_resend_uses_the_current_address_and_keeps_history(db, mail):
    row = gave_up(db, mail)
    with database.get_connection() as connection:
        connection.execute("UPDATE employees SET email='fixed@example.test' WHERE employee_id='a'")
        connection.commit()
    email_status.resend(row["notification_id"], OWNER)
    after = row_for("a")
    assert (after["state"], after["email"], after["attempts"]) == (
        "queued",
        "fixed@example.test",
        None,
    )
    run_round(db)
    assert row_for("a")["state"] == "accepted"
    with database.get_connection() as connection:
        attempts = connection.execute(
            "SELECT COUNT(*) AS n FROM email_delivery_attempts WHERE notification_id = ?",
            (row["notification_id"],),
        ).fetchone()["n"]
    assert attempts == 3


def test_resend_is_refused_for_a_completed_assignment(db, mail):
    row = gave_up(db, mail)
    current = _progress.get_for_employee("a")["course"]
    current.update(status="completed", completed_at=START.isoformat())
    _progress.save("a", "course", current)
    with pytest.raises(ConflictError):
        email_status.resend(row["notification_id"], OWNER)


def test_resend_is_refused_without_a_valid_address(db, mail):
    row = gave_up(db, mail)
    with database.get_connection() as connection:
        connection.execute("UPDATE employees SET email=NULL WHERE employee_id='a'")
        connection.commit()
    with pytest.raises(ConflictError):
        email_status.resend(row["notification_id"], OWNER)


def test_concurrent_resends_only_one_wins(db, mail):
    row = gave_up(db, mail)

    def attempt(_):
        try:
            email_status.resend(row["notification_id"], OWNER)
            return "ok"
        except ConflictError:
            return "conflict"

    with ThreadPoolExecutor(2) as pool:
        outcomes = sorted(pool.map(attempt, range(2)))
    assert outcomes == ["conflict", "ok"]


def test_bulk_resend_excludes_unknown(db, mail, monkeypatch):
    gave_up(db, mail, "failed")
    enrol("crashed")
    with monkeypatch.context() as patch:
        patch.setattr(outbox, "_send_notification", lambda n: (_ for _ in ()).throw(_Crash()))
        with pytest.raises(_Crash):
            outbox.process_pending_notifications()
    db.advance(minutes=11)
    assert email_status.resend_failed(SCOPE, OWNER, course_id="course") == {"resent": 1, "skipped": 0}
    assert row_for("crashed")["state"] == "unknown"
    assert row_for("failed")["state"] == "queued"


def test_other_trainers_see_masked_addresses_and_cannot_resend(db, mail):
    row = gave_up(db, mail)
    other = row_for("a", scope=OTHER_SCOPE, trainer=OTHER)
    assert other["email"] == "a***@example.test"
    assert other["can_resend"] is False
    assert report(scope=OTHER_SCOPE, trainer=OTHER)["can_resend"] is False
    with pytest.raises(AuthorizationError):
        email_status.resend(row["notification_id"], OTHER)
    with pytest.raises(AuthorizationError):
        email_status.resend_failed(OTHER_SCOPE, OTHER, course_id="course")
    exported = email_status.csv_rows(OTHER_SCOPE, OTHER, course_id="course")
    assert exported[0]["email"] == "a***@example.test"
    assert report(scope=OTHER_SCOPE, trainer=OTHER, search="a@example")["matched"] == 0


def test_tiles_always_add_up_to_the_course(db, mail, monkeypatch):
    mail.behaviours[:] = ["no_mailbox", "busy"]
    for employee in ("a", "b", "c", "d"):
        enrol(employee)
    enrol("no_address", email=None)
    run_round(db)
    result = report()
    tiles = {tile["key"]: tile["count"] for tile in result["tiles"]}
    assert tiles.pop("all") == result["total"] == 5
    assert sum(tiles.values()) == 5


def test_filters_and_paging_do_not_change_the_tiles(db, mail):
    for employee in ("a", "b", "c"):
        enrol(employee)
    run_round(db)
    full = report()
    filtered = report(tile="gave_up", search="zzz", page=1, page_size=1)
    assert filtered["tiles"] == full["tiles"]
    assert filtered["matched"] == 0
    assert len(report(page_size=2)["rows"]) == 2
    assert report(page_size=2)["matched"] == 3


def test_activity_matches_the_employees_report(db, mail):
    enrol("started")
    enrol("idle")
    current = _progress.get_for_employee("started")["course"]
    current.update(status="started", started_at=START.isoformat())
    _progress.save("started", "course", current)
    run_round(db)
    total, rows = performance_reporting.employee_page(
        SCOPE,
        search=None,
        attention=None,
        sort="employee",
        descending=False,
        page=1,
        page_size=50,
        now=db.now,
        course_id="course",
    )
    by_id = {row["employee_id"]: row for row in rows}
    assert total["employees"] == 2
    assert row_for("started")["activity_state"] == "in_progress"
    assert by_id["started"]["in_progress"] == 1
    assert row_for("idle")["activity_state"] == "not_started"
    assert by_id["idle"]["not_started"] == 1
    result = report(not_started=True)
    assert [r["employee_id"] for r in result["rows"]] == ["idle"]
    assert result["not_started_count"] == 1


def test_worker_heartbeat_drives_the_banner(db, mail):
    enrol("a")
    assert report()["banners"][0]["kind"] == "worker"
    outbox.run_notification_cycle()
    result = report()
    assert result["banners"] == []
    assert result["last_send_round"]
    db.advance(seconds=settings.email_scheduler_interval_seconds * 4)
    assert report()["banners"][0]["kind"] == "worker"


def test_existing_databases_gain_the_tracking_tables(db):
    with database.get_connection() as connection:
        schema._create_tables(connection.cursor())
        connection.commit()
