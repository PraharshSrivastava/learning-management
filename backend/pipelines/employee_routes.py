import asyncio
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from core.database import (
    delete_employee_course_progress,
    employee_matches_assignment_rule,
    get_assignment_rule,
    get_all_courses,
    get_course_employee_progress,
    get_employee,
    get_employee_assignment_options,
    get_employee_progress,
    list_employee_course_progress,
    list_employees,
    matching_employees_for_assignment_rule,
    save_assignment_rule,
    save_employee_course_progress,
)

router = APIRouter()

_demo_sessions: Dict[str, str] = {}
_active_websockets: Dict[str, List[WebSocket]] = {}


class DemoLoginRequest(BaseModel):
    employee_id: str


def _course_public_id(course: dict) -> Optional[str]:
    return course.get("course_id") or course.get("id")


def _course_is_publishable(course: dict) -> bool:
    modules = course.get("modules") or []
    if not modules:
        return False

    for module in modules:
        if not module.get("video_path"):
            return False
        try:
            num_questions = int(module.get("num_questions", 0))
        except (TypeError, ValueError):
            num_questions = 0
        if num_questions <= 0:
            continue
        quiz = module.get("quiz")
        if not isinstance(quiz, dict) or not quiz.get("questions"):
            return False

    return True


def _published_course_ids() -> set[str]:
    return {
        course_id
        for course_id in (_course_public_id(course) for course in get_all_courses("published"))
        if course_id
    }


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _course_title(course: dict) -> str:
    return course.get("title") or course.get("course_name") or _course_public_id(course) or "Untitled course"


def _performance_status(progress: dict, now: datetime) -> Dict[str, str]:
    status = (progress.get("status") or "pending").lower()
    deadline = _parse_datetime(progress.get("deadline"))
    if status == "completed":
        return {"key": "completed", "label": "Completed"}
    if deadline and now > deadline:
        return {"key": "overdue", "label": "Overdue"}
    if status == "started":
        return {"key": "started", "label": "Started"}
    return {"key": "pending", "label": "Pending"}


def _module_performance(course: dict, progress: dict) -> Dict[str, object]:
    modules = course.get("modules") or []
    progress_by_module = progress.get("modules") or {}
    attempts_by_module = progress.get("attempts") or {}
    details = []
    completed = 0
    total_attempts = 0
    scores = []
    latest_score = None
    latest_attempt_at = None

    for module in modules:
        module_number = str(module.get("module_number", len(details) + 1))
        module_progress = progress_by_module.get(module_number, {})
        attempt = attempts_by_module.get(module_number, {})
        attempt_count = int(attempt.get("count") or 0)
        total_attempts += attempt_count
        score = module_progress.get("quiz_score", attempt.get("last_score"))
        if isinstance(score, (int, float)):
            scores.append(float(score))
        attempt_at = _parse_datetime(attempt.get("last_attempt_at"))
        if attempt_at and (latest_attempt_at is None or attempt_at > latest_attempt_at):
            latest_attempt_at = attempt_at
            latest_score = score
        video_watched = bool(module_progress.get("video_watched"))
        quiz_required = bool(module.get("quiz"))
        quiz_passed = bool(module_progress.get("quiz_passed")) or (
            not quiz_required and video_watched
        )
        if video_watched and quiz_passed:
            completed += 1
        details.append(
            {
                "module_number": int(module.get("module_number", len(details) + 1)),
                "title": module.get("title", f"Module {module_number}"),
                "video_watched": video_watched,
                "quiz_passed": quiz_passed,
                "quiz_score": score,
                "attempt_count": attempt_count,
                "last_score": attempt.get("last_score"),
                "last_passed": attempt.get("last_passed"),
                "last_attempt_at": attempt.get("last_attempt_at"),
            }
        )

    total = len(modules)
    return {
        "total_modules": total,
        "completed_modules": completed,
        "completion_percent": round((completed / total) * 100) if total else 0,
        "total_attempts": total_attempts,
        "latest_score": latest_score,
        "best_score": max(scores) if scores else None,
        "average_score": round(sum(scores) / len(scores), 2) if scores else None,
        "modules": details,
    }


def _new_breakdown(label: str) -> Dict[str, object]:
    return {
        "label": label,
        "assigned": 0,
        "pending": 0,
        "started": 0,
        "completed": 0,
        "overdue": 0,
        "completion_rate": 0,
    }


def _add_breakdown_count(groups: Dict[str, Dict[str, object]], label: str, status_key: str):
    group = groups.setdefault(label, _new_breakdown(label))
    group["assigned"] += 1
    group[status_key] += 1


def _finalize_breakdowns(groups: Dict[str, Dict[str, object]]) -> List[Dict[str, object]]:
    values = list(groups.values())
    for group in values:
        assigned = group["assigned"]
        group["completion_rate"] = round((group["completed"] / assigned) * 100) if assigned else 0
    return sorted(values, key=lambda item: (-item["assigned"], str(item["label"])))


def _authorization_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization token")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid authorization token")
    return token


def _employee_id_from_token(token: str) -> str:
    employee_id = _demo_sessions.get(token)
    if not employee_id:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return employee_id


def _current_employee(authorization: Optional[str]) -> dict:
    token = _authorization_token(authorization)
    employee_id = _employee_id_from_token(token)
    employee = get_employee(employee_id)
    if not employee or employee.get("status") != "active":
        raise HTTPException(status_code=401, detail="Employee is not active")
    return employee


def ensure_assignments_for_employee(employee_id: str) -> bool:
    """Assign currently relevant published courses to one employee."""
    employee = get_employee(employee_id)
    if not employee or employee.get("status") != "active":
        return False
    published_courses = get_all_courses("published")
    progress = get_employee_progress(employee_id)
    now = datetime.now()
    updated = False

    for course in published_courses:
        course_id = _course_public_id(course)
        if not course_id or course_id in progress:
            continue
        rule = get_assignment_rule(course_id)
        if not rule.get("published_at"):
            continue
        if not employee_matches_assignment_rule(employee, rule, now):
            continue
        save_employee_course_progress(
            employee_id,
            course_id,
            {
                "status": "pending",
                "assigned_at": now.isoformat(),
                "deadline": (now + timedelta(days=rule["deadline_days"])).isoformat(),
                "modules": {},
                "attempts": {},
                "last_activity_at": now.isoformat(),
            },
        )
        updated = True

    return updated


def get_enriched_employee_courses(employee_id: str):
    ensure_assignments_for_employee(employee_id)
    courses = get_all_courses("published")
    progress = get_employee_progress(employee_id)
    now = datetime.now()
    progress_updated = False
    employee_courses = []

    for course in courses:
        course_id = _course_public_id(course)
        if not course_id:
            continue
        rule = get_assignment_rule(course_id)
        employee = get_employee(employee_id)
        if (
            not employee
            or not rule.get("published_at")
            or not employee_matches_assignment_rule(employee, rule, now)
        ):
            continue
        course_progress = progress.get(course_id)
        if not course_progress:
            continue

        if "modules" not in course_progress:
            course_progress["modules"] = {}
            progress_updated = True
        if "attempts" not in course_progress:
            course_progress["attempts"] = {}
            progress_updated = True

        if course_progress["status"] in ["pending", "started"]:
            deadline_dt = datetime.fromisoformat(course_progress["deadline"])
            if now > deadline_dt:
                course_progress["status"] = "overdue"
                progress_updated = True

        enriched = dict(course)
        enriched["employee_status"] = course_progress["status"]
        enriched["assigned_at"] = course_progress["assigned_at"]
        enriched["deadline"] = course_progress["deadline"]
        enriched["started_at"] = course_progress.get("started_at")
        enriched["completed_at"] = course_progress.get("completed_at")
        enriched["employee_progress"] = course_progress.get("modules", {})
        enriched["employee_attempts"] = course_progress.get("attempts", {})
        employee_courses.append(enriched)

        if progress_updated:
            save_employee_course_progress(employee_id, course_id, course_progress)

    return employee_courses


async def broadcast_employee_courses(employee_id: str):
    sockets = _active_websockets.get(employee_id, [])
    if not sockets:
        return

    data = get_enriched_employee_courses(employee_id)
    closed = []
    for ws in sockets:
        try:
            await ws.send_json(data)
        except Exception:
            closed.append(ws)

    for ws in closed:
        if ws in sockets:
            sockets.remove(ws)


def _schedule_employee_broadcast(employee_id: str):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_employee_courses(employee_id))
    except RuntimeError:
        asyncio.run(broadcast_employee_courses(employee_id))
    except Exception:
        pass


def assign_published_courses_to_employees(published_courses=None):
    """Called by the exporter after published courses are synchronized."""
    for employee in list_employees():
        employee_id = employee["id"]
        changed = ensure_assignments_for_employee(employee_id)
        if changed:
            _schedule_employee_broadcast(employee_id)


def assign_published_course_to_matching_employees(course_id: str, deadline_changed: bool = False):
    now = datetime.now()
    rule = get_assignment_rule(course_id)
    if not rule.get("published_at"):
        return {"assigned": 0, "removed": 0, "deadline_updates": 0}
    if course_id not in _published_course_ids():
        return {"assigned": 0, "removed": 0, "deadline_updates": 0}
    matched_employees = matching_employees_for_assignment_rule(rule)
    matched_by_id = {employee["id"]: employee for employee in matched_employees}
    existing_progress = get_course_employee_progress(course_id)
    assigned = 0
    removed = 0
    deadline_updates = 0

    for employee_id in list(existing_progress.keys()):
        if employee_id not in matched_by_id:
            delete_employee_course_progress(employee_id, course_id)
            removed += 1
            _schedule_employee_broadcast(employee_id)

    for employee in matched_employees:
        employee_id = employee["id"]
        if employee_id in existing_progress:
            if deadline_changed:
                course_progress = existing_progress[employee_id]
                course_progress["deadline"] = (now + timedelta(days=rule["deadline_days"])).isoformat()
                course_progress["last_activity_at"] = now.isoformat()
                save_employee_course_progress(employee_id, course_id, course_progress)
                deadline_updates += 1
                _schedule_employee_broadcast(employee_id)
            continue
        save_employee_course_progress(
            employee_id,
            course_id,
            {
                "status": "pending",
                "assigned_at": now.isoformat(),
                "deadline": (now + timedelta(days=rule["deadline_days"])).isoformat(),
                "modules": {},
                "attempts": {},
                "last_activity_at": now.isoformat(),
            },
        )
        assigned += 1
        _schedule_employee_broadcast(employee_id)
    return {"assigned": assigned, "removed": removed, "deadline_updates": deadline_updates}


@router.get("/api/employees")
def api_list_employees():
    return list_employees()


@router.get("/api/assignment/options")
def api_assignment_options():
    return get_employee_assignment_options()


@router.get("/api/assignment/courses")
def api_assignable_courses():
    return [
        course
        for course in get_all_courses("draft")
        if _course_public_id(course) and _course_is_publishable(course)
    ]


@router.get("/api/trainer/performance")
def api_trainer_performance(
    course_id: Optional[str] = None,
    employee_id: Optional[str] = None,
    department: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    joined_less_than_days_ago: Optional[int] = None,
):
    now = datetime.now()
    employees = {
        employee["id"]: employee
        for employee in list_employees(include_inactive=True)
    }
    courses = {
        _course_public_id(course): course
        for course in get_all_courses("published")
        if _course_public_id(course)
    }
    rows = []
    summary = {
        "assigned": 0,
        "pending": 0,
        "started": 0,
        "completed": 0,
        "overdue": 0,
        "completion_rate": 0,
        "average_attempts": 0,
        "average_score": None,
    }
    course_groups: Dict[str, Dict[str, object]] = {}
    department_groups: Dict[str, Dict[str, object]] = {}
    role_groups: Dict[str, Dict[str, object]] = {}
    total_attempts = 0
    scores = []

    for progress in list_employee_course_progress():
        employee = employees.get(progress["employee_id"])
        course = courses.get(progress["course_id"])
        if not employee or not course:
            continue

        status_info = _performance_status(progress, now)
        if course_id and progress["course_id"] != course_id:
            continue
        if employee_id and progress["employee_id"] != employee_id:
            continue
        if department and employee.get("department") != department:
            continue
        if role and employee.get("role") != role:
            continue
        if joined_less_than_days_ago is not None:
            try:
                join_date = datetime.fromisoformat(employee["join_date"]).date()
            except (KeyError, TypeError, ValueError):
                continue
            if (now.date() - join_date).days >= joined_less_than_days_ago:
                continue
        if status and status_info["key"] != status:
            continue

        metrics = _module_performance(course, progress)
        total_attempts += int(metrics["total_attempts"])
        if isinstance(metrics["average_score"], (int, float)):
            scores.append(float(metrics["average_score"]))

        summary["assigned"] += 1
        summary[status_info["key"]] += 1
        _add_breakdown_count(course_groups, _course_title(course), status_info["key"])
        _add_breakdown_count(department_groups, employee.get("department") or "Unassigned", status_info["key"])
        _add_breakdown_count(role_groups, employee.get("role") or "Unassigned", status_info["key"])

        rows.append(
            {
                "employee": {
                    "id": employee["id"],
                    "name": employee["name"],
                    "employee_code": employee["employee_code"],
                    "department": employee["department"],
                    "role": employee["role"],
                    "join_date": employee["join_date"],
                    "status": employee["status"],
                },
                "course": {
                    "id": progress["course_id"],
                    "title": _course_title(course),
                    "module_count": len(course.get("modules") or []),
                },
                "status": status_info,
                "assigned_at": progress.get("assigned_at"),
                "deadline": progress.get("deadline"),
                "started_at": progress.get("started_at"),
                "completed_at": progress.get("completed_at"),
                "last_activity_at": progress.get("last_activity_at"),
                **metrics,
            }
        )

    if summary["assigned"]:
        summary["completion_rate"] = round((summary["completed"] / summary["assigned"]) * 100)
        summary["average_attempts"] = round(total_attempts / summary["assigned"], 2)
    if scores:
        summary["average_score"] = round(sum(scores) / len(scores), 2)

    rows.sort(
        key=lambda item: (
            item["status"]["key"] != "overdue",
            item["deadline"] or "",
            item["employee"]["name"],
        )
    )

    options = get_employee_assignment_options()
    options["courses"] = [
        {"id": course_id, "title": _course_title(course)}
        for course_id, course in sorted(courses.items(), key=lambda item: _course_title(item[1]))
    ]
    options["statuses"] = [
        {"key": "pending", "label": "Pending"},
        {"key": "started", "label": "Started"},
        {"key": "completed", "label": "Completed"},
        {"key": "overdue", "label": "Overdue"},
    ]

    return {
        "summary": summary,
        "breakdowns": {
            "courses": _finalize_breakdowns(course_groups),
            "departments": _finalize_breakdowns(department_groups),
            "roles": _finalize_breakdowns(role_groups),
        },
        "rows": rows,
        "options": options,
        "generated_at": now.isoformat(),
    }


@router.get("/api/courses/{course_id}/assignment")
def api_get_course_assignment(course_id: str):
    rule = get_assignment_rule(course_id)
    matches = matching_employees_for_assignment_rule(rule, limit=10)
    return {
        "rule": rule,
        "match_count": len(matching_employees_for_assignment_rule(rule)),
        "preview_employees": matches,
    }


@router.put("/api/courses/{course_id}/assignment")
def api_save_course_assignment(course_id: str, payload: dict):
    rule = save_assignment_rule(course_id, payload)
    matches = matching_employees_for_assignment_rule(rule, limit=10)
    return {
        "rule": rule,
        "match_count": len(matching_employees_for_assignment_rule(rule)),
        "preview_employees": matches,
    }


@router.post("/api/courses/{course_id}/publish-assignment")
def api_publish_course_assignment(course_id: str, payload: dict):
    previous_rule = get_assignment_rule(course_id)
    rule = save_assignment_rule(course_id, payload)
    draft_course = next(
        (course for course in get_all_courses("draft") if _course_public_id(course) == course_id),
        None,
    )
    if not draft_course or not _course_is_publishable(draft_course):
        raise HTTPException(
            status_code=400,
            detail="Course is not ready for assignment. Generate all videos and quizzes first.",
        )
    try:
        from pipelines.exporter import sync_clean_database
        sync_clean_database()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to publish courses: {exc}")
    if course_id not in _published_course_ids():
        raise HTTPException(
            status_code=400,
            detail="Course could not be published yet. Generate all videos and quizzes first.",
        )
    rule = save_assignment_rule(course_id, rule, publish=True)
    changes = assign_published_course_to_matching_employees(
        course_id,
        deadline_changed=(
            previous_rule.get("applied_deadline_days", previous_rule.get("deadline_days"))
            != rule.get("deadline_days")
        ),
    )
    matches = matching_employees_for_assignment_rule(rule, limit=10)
    return {
        "rule": rule,
        "assigned_count": changes["assigned"],
        "removed_count": changes["removed"],
        "deadline_update_count": changes["deadline_updates"],
        "match_count": len(matching_employees_for_assignment_rule(rule)),
        "preview_employees": matches,
    }


@router.post("/api/auth/demo-login")
def demo_login(payload: DemoLoginRequest):
    employee = get_employee(payload.employee_id)
    if not employee or employee.get("status") != "active":
        raise HTTPException(status_code=404, detail="Active employee not found")
    token = secrets.token_urlsafe(32)
    _demo_sessions[token] = employee["id"]
    ensure_assignments_for_employee(employee["id"])
    return {"token": token, "employee": employee}


@router.get("/api/me")
def api_me(authorization: Optional[str] = Header(default=None)):
    return _current_employee(authorization)


@router.get("/api/me/courses")
def api_my_courses(authorization: Optional[str] = Header(default=None)):
    employee = _current_employee(authorization)
    return get_enriched_employee_courses(employee["id"])


@router.websocket("/api/me/courses/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    try:
        employee_id = _employee_id_from_token(token)
    except HTTPException:
        await websocket.close(code=1008)
        return
    employee = get_employee(employee_id)
    if not employee or employee.get("status") != "active":
        await websocket.close(code=1008)
        return

    await websocket.accept()
    sockets = _active_websockets.setdefault(employee_id, [])
    sockets.append(websocket)
    try:
        await websocket.send_json(get_enriched_employee_courses(employee_id))
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in sockets:
            sockets.remove(websocket)


@router.put("/api/me/courses/{course_id}/status")
async def update_course_status(
    course_id: str,
    payload: dict,
    authorization: Optional[str] = Header(default=None),
):
    employee = _current_employee(authorization)
    employee_id = employee["id"]
    ensure_assignments_for_employee(employee_id)
    new_status = payload.get("status")
    if new_status not in ["pending", "started", "completed", "overdue"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    progress = get_employee_progress(employee_id)
    if course_id not in progress:
        raise HTTPException(status_code=404, detail="Course not assigned to employee")

    now = datetime.now().isoformat()
    course_progress = progress[course_id]
    course_progress["status"] = new_status
    course_progress["last_activity_at"] = now
    if new_status == "started" and not course_progress.get("started_at"):
        course_progress["started_at"] = now
    if new_status == "completed":
        course_progress["completed_at"] = now

    save_employee_course_progress(employee_id, course_id, course_progress)
    await broadcast_employee_courses(employee_id)
    return {"message": "Status updated", "status": new_status}


@router.put("/api/me/courses/{course_id}/modules/{module_number}")
async def update_module_progress(
    course_id: str,
    module_number: str,
    payload: dict,
    authorization: Optional[str] = Header(default=None),
):
    employee = _current_employee(authorization)
    employee_id = employee["id"]
    ensure_assignments_for_employee(employee_id)
    progress = get_employee_progress(employee_id)
    if course_id not in progress:
        raise HTTPException(status_code=404, detail="Course not assigned")

    now = datetime.now().isoformat()
    course_progress = progress[course_id]
    course_progress.setdefault("modules", {})
    course_progress.setdefault("attempts", {})
    course_progress["last_activity_at"] = now

    if course_progress["status"] == "pending":
        course_progress["status"] = "started"
        course_progress["started_at"] = now

    mod_prog = course_progress["modules"].get(module_number, {})
    if "video_watched" in payload:
        mod_prog["video_watched"] = payload["video_watched"]
        mod_prog["video_watched_at"] = now if payload["video_watched"] else None
    if "quiz_passed" in payload:
        mod_prog["quiz_passed"] = payload["quiz_passed"]
    if "quiz_score" in payload:
        mod_prog["quiz_score"] = payload["quiz_score"]
    if "selected_answers" in payload:
        mod_prog["selected_answers"] = payload["selected_answers"]

    if "quiz_passed" in payload or "quiz_score" in payload:
        attempt = course_progress["attempts"].get(module_number, {"count": 0})
        attempt["count"] = int(attempt.get("count", 0)) + 1
        attempt["last_attempt_at"] = now
        attempt["last_score"] = payload.get("quiz_score")
        attempt["last_passed"] = payload.get("quiz_passed")
        course_progress["attempts"][module_number] = attempt

    course_progress["modules"][module_number] = mod_prog

    published_courses = get_all_courses("published")
    for pub_course in published_courses:
        if _course_public_id(pub_course) == course_id:
            modules = pub_course.get("modules", [])
            total_modules = len(modules)
            completed_count = 0
            for module in modules:
                module_number_key = str(module.get("module_number", ""))
                module_progress = course_progress["modules"].get(module_number_key, {})
                video_watched = bool(module_progress.get("video_watched"))
                quiz_required = bool(module.get("quiz"))
                quiz_passed = bool(module_progress.get("quiz_passed")) or (
                    not quiz_required and video_watched
                )
                if video_watched and quiz_passed:
                    completed_count += 1
            if total_modules > 0 and completed_count == total_modules:
                course_progress["status"] = "completed"
                course_progress["completed_at"] = now
            elif course_progress["status"] == "pending":
                course_progress["status"] = "started"
                course_progress["started_at"] = now
            break

    save_employee_course_progress(employee_id, course_id, course_progress)
    await broadcast_employee_courses(employee_id)
    return {"message": "Module progress updated"}
