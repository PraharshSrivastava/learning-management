"""Seed an isolated local database with synthetic Performance-tab data.

Run only with DATABASE_URL pointing to a database named lms_performance_demo.
The script never clears existing records and refuses to reseed an existing demo.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.repositories.database import get_connection
from app.repositories.schema import init_db

TRAINER_ID = "demo-trainer"
FIRST_NAMES = (
    "Aarav", "Aisha", "Anaya", "Arjun", "Diya", "Ishaan", "Kavya", "Meera", "Neha", "Rohan",
)
LAST_NAMES = (
    "Bose", "Desai", "Iyer", "Kapoor", "Mehta", "Nair", "Patel", "Rao", "Shah", "Verma",
)
DEPARTMENTS = ("Sales", "Operations", "Risk", "Support", "Branch Network")
COURSES = (
    ("compliance", "Compliance Essentials", ("Policies and conduct", "KYC checks", "Scenario review")),
    ("products", "Product Knowledge", ("Product landscape", "Suitability", "Client questions")),
    ("conversations", "Client Conversations", ("Preparation", "Active listening", "Follow-up")),
    ("risk", "Risk Management", ("Risk basics", "Controls", "Incident response")),
)


def _date(now: datetime, days: int) -> str:
    return (now + timedelta(days=days)).isoformat()


def seed() -> None:
    with get_connection() as connection:
        database = connection.execute("SELECT current_database() AS name").fetchone()["name"]
        if database != "lms_performance_demo":
            raise RuntimeError("Refusing to seed outside lms_performance_demo")
    init_db()
    now = datetime.now()
    with get_connection() as connection:
        if connection.execute(
            "SELECT 1 FROM trainers WHERE trainer_id = ?", (TRAINER_ID,)
        ).fetchone():
            print("Performance demo already seeded; no records changed.")
            return
        connection.execute(
            "INSERT INTO employees (employee_id, name, job_title, source) VALUES (?, ?, ?, 'hub')",
            (TRAINER_ID, "Performance Demo Trainer", "Trainer"),
        )
        connection.execute(
            "INSERT INTO trainers (trainer_id, name) VALUES (?, ?)",
            (TRAINER_ID, "Performance Demo Trainer"),
        )
        for course_key, name, modules in COURSES:
            course_id = f"demo-course-{course_key}"
            connection.execute(
                "INSERT INTO courses (course_id, trainer_id, course_name, status, published_at) "
                "VALUES (?, ?, ?, 'published', ?)",
                (course_id, TRAINER_ID, name, _date(now, -90)),
            )
            connection.execute(
                "INSERT INTO assignment_rules (course_id, published_at) VALUES (?, ?)",
                (course_id, _date(now, -90)),
            )
            for module_number, title in enumerate(modules, start=1):
                connection.execute(
                    "INSERT INTO course_modules (module_id, course_id, module_number, title, num_questions) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        f"demo-module-{course_key}-{module_number}",
                        course_id,
                        module_number,
                        title,
                        0 if module_number == 1 else 5,
                    ),
                )

        for learner_index in range(100):
            employee_id = f"demo-learner-{learner_index + 1:03d}"
            name = (
                f"{FIRST_NAMES[learner_index // 10]} "
                f"{LAST_NAMES[learner_index % 10]}"
            )
            department = DEPARTMENTS[learner_index % len(DEPARTMENTS)]
            connection.execute(
                "INSERT INTO employees (employee_id, name, job_title, department, join_date, source) "
                "VALUES (?, ?, 'Learner', ?, ?, 'manual')",
                (employee_id, name, department, _date(now, -(15 + learner_index % 400))),
            )
            cohort = "Cohort A" if learner_index % 2 == 0 else "Cohort B"
            connection.execute(
                "INSERT INTO employee_groups (employee_id, group_dn, group_cn) VALUES (?, ?, ?)",
                (employee_id, f"cn={cohort},dc=demo", cohort),
            )
            if learner_index % 5 == 0:
                connection.execute(
                    "INSERT INTO employee_groups (employee_id, group_dn, group_cn) VALUES (?, ?, ?)",
                    (employee_id, "cn=Team Leads,dc=demo", "Team Leads"),
                )

            for course_index, (course_key, _, _) in enumerate(COURSES):
                course_id = f"demo-course-{course_key}"
                assignment_id = f"demo-assignment-{course_key}-{learner_index + 1:03d}"
                bucket = (learner_index + course_index * 3) % 10
                if bucket < 4:
                    status = "completed"
                    completed_days = -(1 + (learner_index * 11 + course_index * 17) % 75)
                    completed_at = _date(now, completed_days)
                    deadline = _date(now, completed_days + (-3 if learner_index % 5 == 0 else 3))
                    assigned_at = _date(now, completed_days - 20)
                    started_at = _date(now, completed_days - 14)
                    activity_at = completed_at
                else:
                    status = "started" if bucket < 7 else "pending"
                    completed_at = None
                    deadline = _date(now, -7 + (learner_index * 7 + course_index * 5) % 29)
                    assigned_at = _date(now, -(10 + learner_index % 40))
                    started_at = _date(now, -(4 + learner_index % 20)) if status == "started" else None
                    activity_at = _date(now, -(1 + learner_index % 20)) if status == "started" else None
                connection.execute(
                    "INSERT INTO course_assignments (assignment_id, course_id, employee_id, status, "
                    "assigned_at, deadline, started_at, completed_at, last_learner_activity_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        assignment_id, course_id, employee_id, status, assigned_at,
                        deadline, started_at, completed_at, activity_at,
                    ),
                )
                if status == "pending":
                    continue
                for module_number in range(1, 4):
                    if status == "started" and module_number == 3:
                        continue
                    module_id = f"demo-module-{course_key}-{module_number}"
                    passed = status == "completed" or module_number == 1
                    watched = status == "completed" or module_number <= 2
                    attempts = 0 if module_number == 1 else (
                        1 + (learner_index + course_index) % 3 if status == "completed" else 2
                    )
                    score = None if attempts == 0 else (
                        round(0.65 + (learner_index % 7) * 0.05, 2) if passed else 0.4
                    )
                    connection.execute(
                        "INSERT INTO module_progress (assignment_id, module_id, video_watched, "
                        "quiz_passed, quiz_score, attempt_count, last_attempt_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            assignment_id, module_id, watched, passed, score, attempts,
                            activity_at if attempts else None,
                        ),
                    )
                    for attempt_index in range(attempts):
                        attempt_passed = passed and attempt_index == attempts - 1
                        connection.execute(
                            "INSERT INTO learning_events (event_id, assignment_id, module_id, "
                            "event_type, occurred_at, score, passed) "
                            "VALUES (?, ?, ?, 'quiz_attempt', ?, ?, ?)",
                            (
                                f"demo-event-{course_key}-{learner_index + 1:03d}-{module_number}-{attempt_index}",
                                assignment_id, module_id,
                                activity_at or _date(now, -1),
                                score if attempt_passed else 0.3 + attempt_index * 0.1,
                                attempt_passed,
                            ),
                        )
        connection.commit()
    print("Seeded 1 trainer, 100 synthetic learners, 4 courses, and 400 assignments.")


if __name__ == "__main__":
    seed()
