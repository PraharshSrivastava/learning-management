"""Real SQL pagination and filters inside a disposable rolled-back schema."""

import os

import pytest
from test_lms_access_postgres import access_db as access_db  # pytest fixture re-export

from app.repositories import courses

pytestmark = pytest.mark.skipif(
    os.getenv("LMS_ACCESS_POSTGRES_TESTS") != "true",
    reason="Requires explicit isolated demo PostgreSQL selection",
)


@pytest.fixture
def library_db(access_db, monkeypatch):
    access_db.execute("CREATE TABLE trainers (trainer_id TEXT PRIMARY KEY, name TEXT)")
    access_db.execute("INSERT INTO trainers VALUES ('t-1', 'Kiran'), ('t-2', 'Karneeshkar')")
    access_db.execute("""CREATE TABLE courses (
        course_id TEXT PRIMARY KEY, trainer_id TEXT, course_name TEXT, course_description TEXT,
        status TEXT, created_at TEXT, updated_at TEXT)""")
    access_db.execute("CREATE TABLE course_generation_status (course_id TEXT PRIMARY KEY, status TEXT)")
    for course_id, owner, status in [("c-1", "t-1", "draft"), ("c-2", "t-2", "published"),
                                      ("c-3", "t-2", "archived")]:
        access_db.execute("INSERT INTO courses VALUES (?, ?, 'Same title', '', ?, '2026-10-06', '2026-10-06')",
                          (course_id, owner, status))
    access_db.execute("INSERT INTO course_generation_status VALUES ('c-2', 'completed')")
    from app.repositories import lms_access
    monkeypatch.setattr(courses, "get_connection", lms_access.get_connection)
    return access_db


def page(**changes):
    params = dict(owner_id=None, status=None, generation_status=None, search=None, limit=2, offset=0)
    params.update(changes)
    return courses.course_library_page(**params)


def test_sql_pagination_is_bounded_and_stable_for_same_title_and_timestamp(library_db):
    first = page()
    second = page(offset=2)
    assert first["total"] == second["total"] == 3
    assert [i["course_id"] for i in first["items"]] == ["c-3", "c-2"]
    assert [i["course_id"] for i in second["items"]] == ["c-1"]
    assert first["items"][0]["creator_name"] == "Karneeshkar"
    assert first["items"][1]["generation_status"] == "completed"
    assert page(offset=99) == {"total": 3, "items": [], "limit": 2, "offset": 99}


@pytest.mark.parametrize("filters,expected", [
    ({"owner_id": "t-1"}, ["c-1"]),
    ({"status": "published"}, ["c-2"]),
    ({"generation_status": "completed"}, ["c-2"]),
    ({"search": "TITLE", "owner_id": "t-2"}, ["c-3", "c-2"]),
    ({"search": "%"}, []),
    ({"owner_id": "' OR TRUE --"}, []),
])
def test_filters_and_untrusted_strings_do_not_expand_scope(library_db, filters, expected):
    result = page(**filters)
    assert [i["course_id"] for i in result["items"]] == expected
    assert result["total"] == len(expected)


def test_owner_lookup_does_not_require_loading_modules(library_db):
    assert courses.get_course_owner("c-2") == "t-2"
    assert courses.get_course_owner("missing") is None
