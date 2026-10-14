"""Asset-to-course lookup and authorization on the real rollback schema."""

import os

import pytest
from psycopg.types.json import Jsonb
from test_observer_reporting_postgres import report_db as report_db

from app.core.exceptions import NotFoundError
from app.repositories import lms_access, observers
from app.schemas.observers import ObserverSaveRequest
from app.services import media_access

pytestmark = pytest.mark.skipif(os.getenv("LMS_ACCESS_POSTGRES_TESTS") != "true", reason="isolated demo opt-in")


def test_asset_lookup_and_normal_trainer_cannot_use_all_performance_as_playback(report_db, monkeypatch):
    monkeypatch.setattr(media_access, "get_connection", observers.get_connection)
    monkeypatch.setattr(lms_access, "get_connection", observers.get_connection)
    from app.services import course_authorization
    monkeypatch.setattr(course_authorization, "_employee_for_trainer", lambda *_: dict(report_db.execute("SELECT * FROM employees WHERE employee_id='hod'").fetchone()))
    monkeypatch.setattr(media_access, "_employee_for_trainer", lambda *_: dict(report_db.execute("SELECT * FROM employees WHERE employee_id='hod'").fetchone()))
    report_db.execute("INSERT INTO course_modules(module_id,course_id,module_number,title,video_path,metadata_json) VALUES ('m-1','course-1',1,'Module','assets/videos/module.mp4',?)",
                      (Jsonb({"images": [{"file_path": "assets/images/private.png"}], "slides": []}),))
    assert media_access.asset_courses("/assets/images/private.png") == ["course-1"]
    assert media_access.asset_courses("/assets/videos/module_hls/segment.ts") == ["course-1"]
    assert media_access.asset_courses("/assets/slides/course-1/module_1.html") == ["course-1"]
    assert media_access.asset_courses("/assets/images/private-other.png") == []
    employee = dict(report_db.execute("SELECT * FROM employees WHERE employee_id='hod'").fetchone())
    normal = media_access.MediaPrincipal("trainer", employee, {"trainer_id": "t-2"})
    with pytest.raises(NotFoundError):
        media_access.authorize_course_media(normal, ["course-1"])
    media_access.authorize_course_media(normal, ["course-2"])
    report_db.execute("INSERT INTO lms_authoring_roles(employee_id,role,identity_key,granted_by) VALUES ('hod','admin_trainer','directory:uuid-hod','fixture')")
    media_access.authorize_course_media(normal, ["course-1"])
    report_db.execute("UPDATE lms_authoring_roles SET active=FALSE")
    with pytest.raises(NotFoundError):
        media_access.authorize_course_media(normal, ["course-1"])


def test_observer_report_grant_does_not_grant_playback_or_documents(report_db, monkeypatch):
    monkeypatch.setattr(media_access, "get_connection", observers.get_connection)
    observers.save_config("course-1", "t-1", ObserverSaveRequest(revision=0, observers=[{
        "observer_employee_id": "observer", "employee_ids": ["b"], "department_ids": []}]))
    observers.apply_config("course-1", "t-1", 1)
    employee = dict(report_db.execute("SELECT * FROM employees WHERE employee_id='observer'").fetchone())
    principal = media_access.MediaPrincipal("employee", employee)
    from app.services import learning

    def no_assignment(*args):
        raise NotFoundError("Course not assigned to employee")

    monkeypatch.setattr(learning, "_assigned_progress_for_employee", no_assignment)
    with pytest.raises(NotFoundError):
        media_access.authorize_course_media(principal, ["course-1"])
    with pytest.raises(NotFoundError):
        media_access.authorize_document(principal, {"trainer_id": "t-1", "document_id": "d-1"})
