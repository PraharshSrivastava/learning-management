"""Exercise real HTTP authorization boundaries without generation/email side effects."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import assignments, course_library, courses, generation
from app.core.exceptions import install_exception_handlers
from app.repositories import courses as repository
from app.repositories import lms_access as grants
from app.services import auth, lms_access
from app.services.course_authorization import READ_ONLY_MESSAGE


@pytest.fixture
def oversight(monkeypatch):
    trainer = {"trainer_id": "t-1", "directory_uuid": "uuid-1", "status": "active"}
    employee = {"employee_id": "e-1", "directory_uuid": "uuid-1", "status": "active"}
    state = {"roles": {"admin_trainer"}, "owner": "t-2", "writes": [], "reads": [], "pages": []}
    monkeypatch.setattr(auth.settings, "hub_launch_dev_mode", True)
    monkeypatch.setattr(auth, "_hub_session", lambda *_: None)
    monkeypatch.setattr(auth, "_local_trainer_sessions", {"trainer-token": "t-1"})
    monkeypatch.setattr(auth, "_local_employee_sessions", {"employee-token": "e-1"})
    monkeypatch.setattr(auth._trainers, "get", lambda *_: trainer)
    monkeypatch.setattr(lms_access._employees, "get_by_directory_uuid", lambda *_: employee)
    monkeypatch.setattr(grants, "access_snapshot", lambda *_: (state["roles"], 1))
    monkeypatch.setattr(repository, "get_course_owner", lambda *_: state["owner"])

    def course_read(course_id, owner_id):
        state["reads"].append(owner_id)
        return {"course_id": course_id, "trainer_id": owner_id, "status": "draft"}

    def assignment_read(course_id, owner_id):
        state["reads"].append(owner_id)
        return {"rule": {"course_id": course_id}, "match_count": 0}

    def job_read(job_id, owner_id):
        state["reads"].append(owner_id)
        return {"id": job_id, "course_id": "c-2", "status": "running", "created_at": "2026-10-06"}

    def page(**kwargs):
        state["pages"].append(kwargs)
        return {"total": 1, "limit": kwargs["limit"], "offset": kwargs["offset"], "items": [{
            "course_id": "c-2", "trainer_id": state["owner"], "creator_name": "Other trainer",
            "course_name": "Same title", "course_description": "", "status": "draft",
            "created_at": "2026-10-06", "updated_at": "2026-10-06",
        }]}

    def write(*args):
        state["writes"].append(args)
        # Fail before any irreversible service side effect; confirms original trainer ID.
        raise AssertionError("creator reached mutation service")

    monkeypatch.setattr(courses.service, "get_course", course_read)
    monkeypatch.setattr(courses, "get_course_creator_name", lambda *_: "Other trainer")
    monkeypatch.setattr(assignments, "api_get_course_assignment", assignment_read)
    monkeypatch.setattr(generation.service.jobs, "get", lambda *_: SimpleNamespace(course_id="c-2"))
    monkeypatch.setattr(generation.service, "get_job", job_read)
    monkeypatch.setattr(repository, "course_library_page", page)
    for name in ("update_course", "delete_course", "update_module_quiz"):
        monkeypatch.setattr(courses.service, name, write)
    for name in ("api_save_course_assignment", "api_publish_course_assignment", "api_disable_course_assignment"):
        monkeypatch.setattr(assignments, name, write)
    for name in ("generate_quiz", "generate_slides", "generate_scripts", "generate_video",
                 "generate_full_course", "start_full_course_job", "continue_generation"):
        monkeypatch.setattr(generation.service, name, write)
    app = FastAPI()
    install_exception_handlers(app)
    for router in (courses.router, assignments.router, generation.router, course_library.router):
        app.include_router(router)
    return TestClient(app), state


def call(client, method, path, **kwargs):
    return client.request(method, path, headers={"Authorization": "Bearer trainer-token"}, **kwargs)


@pytest.mark.parametrize("path", ["/api/courses/c-2", "/api/courses/c-2/assignment"])
def test_admin_reads_with_owner_scope_and_revoke_blocks_same_session(oversight, path):
    client, state = oversight
    assert call(client, "GET", path).status_code == 200
    assert state["reads"] == ["t-2"]
    state["roles"] = set()
    assert call(client, "GET", path).status_code == 404
    assert state["reads"] == ["t-2"]


def test_job_read_checks_course_and_current_grant(oversight):
    client, state = oversight
    response = call(client, "GET", "/api/generation-jobs/job-2")
    assert response.status_code == 200 and response.json()["status"] == "running"
    assert response.headers["cache-control"] == "no-store"
    assert state["reads"] == ["t-2"]
    state["roles"] = set()
    assert call(client, "GET", "/api/generation-jobs/job-2").status_code == 404
    assert state["reads"] == ["t-2"]


MUTATIONS = [
    ("PUT", "/api/courses/c-2", {}),
    ("DELETE", "/api/courses/c-2", None),
    ("PUT", "/api/courses/c-2/modules/1/quiz", {"questions": [{
        "question_text": "Question", "options": [{"key": "A", "text": "Answer"}],
        "correct_option": "A",
    }]}),
    ("PUT", "/api/courses/c-2/assignment", {}),
    ("POST", "/api/courses/c-2/publish-assignment", {}),
    ("POST", "/api/courses/c-2/disable-assignment", None),
    *[("POST", "/api/courses/c-2/" + suffix, None) for suffix in (
        "generate-quiz", "generate-slides", "generate-scripts", "generate-full-course",
        "generation-jobs", "continue-generation", "modules/1/generate-video",
    )],
]


@pytest.mark.parametrize("method,path,payload", MUTATIONS)
def test_cross_owner_mutations_never_reach_services(oversight, method, path, payload):
    client, state = oversight
    kwargs = {"json": payload} if payload is not None else {}
    response = call(client, method, path, **kwargs)
    assert response.status_code == 403
    assert response.json()["detail"] == READ_ONLY_MESSAGE
    state["roles"] = set()
    assert call(client, method, path, **kwargs).status_code == 404
    assert state["writes"] == []


@pytest.mark.parametrize("method,path,payload", MUTATIONS)
def test_creator_retains_original_mutation_path(oversight, method, path, payload):
    client, state = oversight
    state.update(owner="t-1", roles=set())
    kwargs = {"json": payload} if payload is not None else {}
    with pytest.raises(AssertionError, match="creator reached"):
        call(client, method, path, **kwargs)
    assert state["writes"][0][-1] == "t-1"


def test_library_defaults_to_own_and_admin_all_is_read_only(oversight):
    client, state = oversight
    state["owner"] = "t-1"
    result = call(client, "GET", "/api/trainer/course-library").json()
    assert result["items"][0]["can_manage"]
    assert state["pages"][-1]["owner_id"] == "t-1"
    state["owner"] = "t-2"
    response = call(client, "GET", "/api/trainer/course-library?scope=all&limit=10&offset=20&search=Title")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert not response.json()["items"][0]["can_manage"]
    assert response.json()["items"][0]["read_only_reason"] == READ_ONLY_MESSAGE
    assert state["pages"][-1]["owner_id"] is None
    state["roles"] = set()
    assert call(client, "GET", "/api/trainer/course-library?scope=all").status_code == 403
    assert call(client, "GET", "/api/trainer/course-library?owner_trainer_id=t-2").status_code == 403


@pytest.mark.parametrize("query", ["limit=101", "offset=-1", "scope=invalid", "status=invalid"])
def test_invalid_library_queries_are_rejected(oversight, query):
    client, state = oversight
    assert call(client, "GET", "/api/trainer/course-library?" + query).status_code == 422
    assert not state["pages"]


@pytest.mark.parametrize("path", ["/api/trainer/course-library?scope=all", "/api/courses/c-2",
                                  "/api/courses/c-2/assignment", "/api/generation-jobs/job-2",
                                  "/api/trainer/course-library/c-2/assignments"])
def test_employee_audience_cannot_use_oversight(oversight, path):
    client, state = oversight
    response = client.get(path, headers={"Authorization": "Bearer employee-token"})
    assert response.status_code == 401
    assert not state["reads"] and not state["pages"]


def test_missing_course_returns_404_without_content_lookup(oversight):
    client, state = oversight
    state["owner"] = None
    assert call(client, "GET", "/api/courses/c-2").status_code == 404
    assert not state["reads"]


def test_inspection_returns_creator_controls_without_changing_legacy_list(oversight, monkeypatch):
    client, state = oversight
    result = call(client, "GET", "/api/courses/c-2").json()
    assert result["creator_name"] == "Other trainer" and not result["can_manage"]
    assert result["read_only_reason"] == READ_ONLY_MESSAGE
    monkeypatch.setattr(courses.service, "list_course_summaries", lambda owner: state["reads"].append(owner) or [])
    result = call(client, "GET", "/api/courses")
    assert result.status_code == 200 and result.json() == []
    assert state["reads"][-1] == "t-1"
    state.update(owner="t-1", roles=set())
    result = call(client, "GET", "/api/courses/c-2").json()
    assert result["can_manage"] and result["read_only_reason"] is None


def test_inactive_canonical_identity_cannot_use_a_stored_admin_grant(oversight, monkeypatch):
    client, state = oversight
    monkeypatch.setattr(lms_access._employees, "get_by_directory_uuid", lambda *_: {
        "employee_id": "e-1", "directory_uuid": "uuid-1", "status": "inactive",
    })
    assert call(client, "GET", "/api/trainer/course-library?scope=all").status_code == 401
    assert call(client, "GET", "/api/courses/c-2").status_code == 401
    assert not state["reads"] and not state["pages"]


def test_missing_job_or_deleted_course_cannot_expose_job_payload(oversight, monkeypatch):
    client, state = oversight
    monkeypatch.setattr(generation.service.jobs, "get", lambda *_: None)
    assert call(client, "GET", "/api/generation-jobs/missing").status_code == 404
    monkeypatch.setattr(generation.service.jobs, "get", lambda *_: SimpleNamespace(course_id="c-2"))
    state["owner"] = None
    assert call(client, "GET", "/api/generation-jobs/deleted-course-job").status_code == 404
    assert not state["reads"]


def test_assigned_learner_inspector_reuses_fixed_course_report_scope(oversight, monkeypatch):
    client, state = oversight
    calls = []

    def report(owner, **kwargs):
        calls.append((owner, kwargs))
        return {"rows": [], "total": 0, "page": kwargs["page"], "page_size": kwargs["page_size"],
                "generated_at": "2026-10-06"}

    monkeypatch.setattr(course_library.reports, "assignment_list", report)
    url = "/api/trainer/course-library/c-2/assignments?page=2&page_size=10&status=completed"
    response = call(client, "GET", url)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert calls == [("t-2", {"course_id": "c-2", "status": "completed", "search": None,
                             "page": 2, "page_size": 10})]
    state["roles"] = set()
    assert call(client, "GET", url).status_code == 404
    assert len(calls) == 1
    state["owner"] = "t-1"
    assert call(client, "GET", url).status_code == 200
    assert calls[-1][0] == "t-1"
