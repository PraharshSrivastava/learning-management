"""Opt-in, read-only PostgreSQL parity checks against a seeded Performance demo.

Run with PERFORMANCE_READONLY_INTEGRATION=true and PERFORMANCE_TEST_TRAINER_ID
set for the isolated demo database. This suite never creates or modifies data.
"""

import os
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime

import pytest

from app.repositories import performance_reporting as repository
from app.services import performance_reporting as service

pytestmark = pytest.mark.skipif(
    os.getenv("PERFORMANCE_READONLY_INTEGRATION") != "true",
    reason="Requires explicitly selected PostgreSQL Performance demo.",
)


@pytest.fixture
def report_data(monkeypatch):
    trainer = os.environ["PERFORMANCE_TEST_TRAINER_ID"]
    original = repository.get_connection

    @contextmanager
    def readonly():
        with original() as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            yield connection

    monkeypatch.setattr(repository, "get_connection", readonly)
    now = datetime.now()
    raw = repository.list_assignment_summaries(trainer)
    assert raw, "Seed the isolated demo before running the opt-in parity checks."
    return trainer, now, raw


@pytest.mark.parametrize("sort", ["employee", "assigned", "completion", "overdue", "score"])
@pytest.mark.parametrize("descending", [False, True])
def test_employee_sql_matches_all_course_aggregation(report_data, sort, descending):
    trainer, now, raw = report_data
    grouped = defaultdict(list)
    for row in raw:
        grouped[row["employee_id"]].append(service._decorate(row, now))
    expected = [service._employee_summary(rows, now) for rows in grouped.values()]
    sort_key = {
        "employee": lambda row: row["employee_name"].lower(),
        "assigned": lambda row: row["assigned"],
        "completion": lambda row: row["completion_rate"],
        "overdue": lambda row: row["overdue"],
        "score": lambda row: row["average_score"] if row["average_score"] is not None else -1,
    }[sort]
    expected.sort(key=lambda row: (sort_key(row), row["employee_id"]), reverse=descending)
    summary, actual = repository.employee_page(
        trainer,
        search=None,
        attention=None,
        sort=sort,
        descending=descending,
        page=1,
        page_size=1,
        now=now,
    )
    assert actual == expected[:1]
    assert summary == {
        "employees": len(expected),
        "assigned": len(raw),
        "completed": sum(row["completed"] for row in expected),
        "overdue": sum(row["overdue"] for row in expected),
    }
    last_summary, empty = repository.employee_page(
        trainer,
        search=None,
        attention=None,
        sort=sort,
        descending=descending,
        page=len(expected) + 1,
        page_size=1,
        now=now,
    )
    assert empty == [] and last_summary == summary


@pytest.mark.parametrize("attention", [None, "needs_attention", "overdue", "completed"])
def test_employee_sql_search_attention_and_scope(report_data, attention):
    trainer, now, raw = report_data
    scope = {"course_id": raw[0]["course_id"], "department": raw[0]["department"]}
    name = raw[0]["employee_name"].upper()
    rows = [
        service._decorate(row, now)
        for row in raw
        if row["course_id"] == scope["course_id"] and row["department"] == scope["department"]
    ]
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["employee_id"]].append(row)
    expected = [service._employee_summary(items, now) for items in grouped.values()]
    expected = [row for row in expected if name.lower() in row["employee_name"].lower()]
    if attention == "needs_attention":
        expected = [row for row in expected if row["needs_attention"]]
    elif attention == "overdue":
        expected = [row for row in expected if row["overdue"]]
    elif attention == "completed":
        expected = [row for row in expected if row["completed"] == row["assigned"]]
    summary, actual = repository.employee_page(
        trainer,
        search=name,
        attention=attention,
        sort="employee",
        descending=False,
        page=1,
        page_size=25,
        now=now,
        **scope,
    )
    assert actual == sorted(
        expected, key=lambda row: (row["employee_name"].lower(), row["employee_id"])
    )
    assert summary["employees"] == len(expected)
    assert summary["assigned"] == sum(row["assigned"] for row in expected)
    other_summary, other_rows = repository.employee_page(
        "non-owning-integration-trainer",
        search=None,
        attention=None,
        sort="employee",
        descending=False,
        page=1,
        page_size=25,
        now=now,
    )
    assert other_rows == [] and other_summary["employees"] == 0


def test_shared_reporting_reads_other_creators_without_widening_content(report_data):
    from app.schemas.reporting_scope import TrainerPerformanceScope

    trainer, now, raw = report_data
    other = "unrelated-reporting-trainer"
    assert repository.list_assignment_summaries(other) == []
    shared = TrainerPerformanceScope(other, all_courses=True)
    all_rows = repository.list_assignment_summaries(shared)
    assert {r["assignment_id"] for r in raw} <= {r["assignment_id"] for r in all_rows}
    row = raw[0]
    assert repository.get_assignment_detail(other, row["assignment_id"]) is None
    assert repository.get_assignment_detail(shared, row["assignment_id"]) is not None
    assert row["course_id"] in {
        c["course_id"] for c in repository.list_scope_options(shared)["courses"]
    }
    assert repository.course_module_summary(shared, row["course_id"])
    summary, page = repository.employee_page(
        shared,
        search=None,
        attention=None,
        sort="employee",
        descending=False,
        page=1,
        page_size=1,
        now=now,
    )
    assert len(page) == 1
    assert summary["assigned"] == len(all_rows)
