"""Development seed data kept separate from schema creation."""

from __future__ import annotations

from datetime import date, datetime, timedelta


def seed_demo_employees(cursor) -> None:
    departments = ["Sales", "Operations", "Compliance", "Risk", "Finance", "HR", "IT", "Research"]
    job_titles = ["Associate", "Senior Associate", "Manager", "Director", "VP"]
    first = ["Aarav", "Ananya", "Rohit", "Sneha", "Vikram", "Neha", "Ishaan", "Priya", "Kabir", "Meera", "Arjun", "Riya"]
    last = ["Mehta", "Khanna", "Iyer", "Shah", "Kapoor", "Rao", "Nair", "Patel", "Menon", "Gupta"]
    today = date.today()
    now = datetime.now().isoformat()
    for index in range(1, 121):
        department = departments[(index - 1) % len(departments)]
        job_title = job_titles[(index - 1) % len(job_titles)]
        offset = (index * 17) % 1095
        if index % 19 == 0:
            offset = index % 30
        employee_id = f"emp_{index:04d}"
        cursor.execute(
            """
            INSERT INTO employees (
                employee_id, name, job_title, department, join_date, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(employee_id) DO NOTHING
            """,
            (
                employee_id,
                f"{first[(index - 1) % len(first)]} {last[(index - 1) % len(last)]}",
                job_title,
                department,
                (today - timedelta(days=offset)).isoformat(),
                "inactive" if index % 37 == 0 else "active",
                now,
                now,
            ),
        )


def seed_demo_trainers(cursor) -> None:
    now = datetime.now().isoformat()
    for trainer_id, name in (
        ("trainer_0001", "Priya Sharma"),
        ("trainer_0002", "Arjun Menon"),
        ("trainer_0003", "Meera Rao"),
    ):
        cursor.execute(
            """
            INSERT INTO trainers (trainer_id, name, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(trainer_id) DO NOTHING
            """,
            (trainer_id, name, "active", now, now),
        )
