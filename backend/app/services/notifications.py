"""Learner-course WebSocket connections and update broadcasts."""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket, WebSocketDisconnect

from app.core.exceptions import AuthenticationError
from app.repositories.employees import EmployeeRepository
from app.security.hub_launch import hub_app_from_header, hub_launch_verifier
from app.services.auth import employee_id_from_token

logger = logging.getLogger(__name__)
_employees = EmployeeRepository()
_active_websockets: dict[str, list[WebSocket]] = {}


async def broadcast_employee_courses(employee_id: str) -> None:
    from app.services.learning import get_enriched_employee_courses

    sockets = _active_websockets.get(employee_id, [])
    if not sockets:
        return
    data = get_enriched_employee_courses(employee_id)
    closed = []
    for websocket in sockets:
        try:
            await websocket.send_json(data)
        except RuntimeError:
            closed.append(websocket)
            logger.warning("employee_websocket_closed employee_id=%s", employee_id)
    for websocket in closed:
        if websocket in sockets:
            sockets.remove(websocket)


def clear_active_websockets() -> None:
    """Reset in-memory websocket state for isolated tests."""
    _active_websockets.clear()


def set_active_websockets_for_tests(employee_id: str, sockets: list[WebSocket]) -> None:
    """Install fake websocket connections for broadcast tests."""
    _active_websockets[employee_id] = sockets


def schedule_employee_broadcast(employee_id: str) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(broadcast_employee_courses(employee_id))
    else:
        loop.create_task(broadcast_employee_courses(employee_id))


async def websocket_endpoint(websocket: WebSocket, token: str = "") -> None:
    """Authenticate employee WebSockets with Hub cookies or explicit local dev sessions."""
    from app.services.learning import get_enriched_employee_courses

    if hub_launch_verifier.config.hub_launch_dev_mode:
        try:
            employee_id = employee_id_from_token(token)
        except AuthenticationError:
            await websocket.close(code=1008)
            return
        employee = _employees.get(employee_id)
    else:
        if hub_app_from_header(websocket.headers.get("x-lms-app")) != "employee":
            await websocket.close(code=1008)
            return
        session = hub_launch_verifier.session_from_request(websocket, "employee")
        employee = _employees.get_by_hub_user_id(session.sub) if session else None
    if not employee or employee.get("status") != "active":
        await websocket.close(code=1008)
        return

    employee_id = employee["employee_id"]
    await websocket.accept()
    sockets = _active_websockets.setdefault(employee_id, [])
    sockets.append(websocket)
    try:
        await websocket.send_json(get_enriched_employee_courses(employee_id))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in sockets:
            sockets.remove(websocket)
