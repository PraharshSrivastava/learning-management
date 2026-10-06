"""Short-lived media credentials with current identity/resource checks on every read."""

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from app.core.exceptions import AuthenticationError, NotFoundError
from app.core.settings import settings
from app.repositories.database import get_connection
from app.repositories.employees import EmployeeRepository
from app.repositories.lms_access import identity_key
from app.repositories.trainers import get_trainer
from app.services.auth import current_employee_from_request, current_trainer_from_request
from app.services.course_authorization import is_admin_trainer
from app.services.lms_access import _employee_for_trainer

_dev_key = secrets.token_bytes(32)
_employees = EmployeeRepository()


@dataclass(frozen=True)
class MediaPrincipal:
    app: str
    employee: dict
    trainer: dict | None = None


def _key():
    return settings.hub_launch_secret.encode() if settings.hub_launch_secret else _dev_key


def issue_media_ticket(request, authorization, app):
    if app == "trainer":
        trainer = current_trainer_from_request(request, authorization)
        employee = _employee_for_trainer(trainer)
    else:
        trainer = None
        employee = current_employee_from_request(request, authorization)
    session = getattr(request.state, "hub_user", None)
    expiry = min(int(time.time()) + 900, int(session["exp"])) if isinstance(session, dict) and session.get("exp") else int(time.time()) + 900
    payload = {"kind": "lms-media-v1", "app": app, "employee_id": employee["employee_id"],
               "identity_key": identity_key(employee), "trainer_id": trainer["trainer_id"] if trainer else None,
               "exp": expiry}
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(_key(), raw.encode(), hashlib.sha256).hexdigest()
    return raw + "." + sig


def media_principal(request, authorization=None):
    ticket = request.query_params.get("media_ticket")
    if ticket:
        try:
            if len(ticket) > 4096:
                raise ValueError()
            raw, signature = ticket.split(".")
            if not hmac.compare_digest(hmac.new(_key(), raw.encode(), hashlib.sha256).hexdigest(), signature):
                raise ValueError()
            payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
            if payload["kind"] != "lms-media-v1" or payload["app"] not in ("employee", "trainer"):
                raise ValueError()
            if payload["exp"] < time.time():
                # Long-running production playback can continue only with the same
                # still-valid Hub cookie, not an expired standalone bearer URL.
                current = current_trainer_from_request(request, authorization) if payload["app"] == "trainer" else current_employee_from_request(request, authorization)
                employee = _employee_for_trainer(current) if payload["app"] == "trainer" else current
                if employee["employee_id"] != payload["employee_id"]:
                    raise ValueError()
            employee = _employees.get(payload["employee_id"])
            if not employee or employee["status"] != "active" or employee.get("directory_status", "active") != "active" or identity_key(employee) != payload["identity_key"]:
                raise ValueError()
            trainer = get_trainer(payload["trainer_id"]) if payload.get("trainer_id") else None
            if payload["app"] == "trainer" and (not trainer or trainer["status"] != "active" or _employee_for_trainer(trainer)["employee_id"] != employee["employee_id"]):
                raise ValueError()
            return MediaPrincipal(payload["app"], employee, trainer)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise AuthenticationError("Invalid or expired media access") from exc
    app = request.headers.get("X-LMS-App")
    if app == "trainer":
        trainer = current_trainer_from_request(request, authorization)
        return MediaPrincipal(app, _employee_for_trainer(trainer), trainer)
    if app == "employee":
        return MediaPrincipal(app, current_employee_from_request(request, authorization))
    raise AuthenticationError("Authenticated media access is required")


def authorize_course_media(principal, course_ids):
    if principal.trainer:
        existing = False
        with get_connection() as db:
            for course_id in course_ids:
                row = db.execute("SELECT trainer_id FROM courses WHERE course_id = ?", (course_id,)).fetchone()
                existing = existing or row is not None
                if row and row["trainer_id"] == principal.trainer["trainer_id"]:
                    return
        if existing and is_admin_trainer(principal.trainer):
            return
    else:
        # HOD/Observer scopes do not confer playback or source-file access.
        from datetime import datetime

        from app.services.learning import _assigned_progress_for_employee
        for course_id in course_ids:
            try:
                _assigned_progress_for_employee(principal.employee, course_id, datetime.now())
                with get_connection() as db:
                    row = db.execute("SELECT status FROM courses WHERE course_id = ?", (course_id,)).fetchone()
                if row and row["status"] == "published":
                    return
            except NotFoundError:
                continue
    raise NotFoundError("Media not found")


def asset_courses(path):
    from psycopg.types.json import Jsonb

    variants = [path, path.lstrip("/")]
    # Slide HTML is stored under a verified course directory.
    parts = path.strip("/").split("/")
    if len(parts) >= 4 and parts[:2] == ["assets", "slides"]:
        with get_connection() as db:
            return [r["course_id"] for r in db.execute("SELECT course_id FROM courses WHERE course_id = ?", (parts[2],)).fetchall()]
    with get_connection() as db:
        rows = db.execute(r"""SELECT DISTINCT c.course_id FROM courses c
            LEFT JOIN course_modules cm ON cm.course_id = c.course_id
            WHERE c.thumbnail_path = ANY(?::text[]) OR cm.video_path = ANY(?::text[])
                OR jsonb_path_exists(c.metadata_json, ('$.** ' || chr(63) || ' (@ == $one || @ == $two)')::jsonpath, ?::jsonb)
                OR jsonb_path_exists(cm.metadata_json, ('$.** ' || chr(63) || ' (@ == $one || @ == $two)')::jsonpath, ?::jsonb)
                OR (cm.video_path ~* '\.mp4$' AND
                    starts_with(?, '/' || ltrim(regexp_replace(cm.video_path, '\.mp4$', '_hls/', 'i'), '/')))
            """, (variants, variants, Jsonb({"one": variants[0], "two": variants[1]}),
                     Jsonb({"one": variants[0], "two": variants[1]}), path)).fetchall()
    return [r["course_id"] for r in rows]


def authorize_document(principal, document):
    if principal.trainer and document:
        if document["trainer_id"] == principal.trainer["trainer_id"]:
            return
        with get_connection() as db:
            linked = db.execute("SELECT course_id FROM courses WHERE document_id = ?", (document["document_id"],)).fetchone()
        if linked and is_admin_trainer(principal.trainer):
            return
    raise NotFoundError("Document not found")
