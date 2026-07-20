import pytest
from starlette.websockets import WebSocketDisconnect

from conftest import auth_headers, login_employee


class FakeWebSocket:
    def __init__(self):
        self.sent_payloads = []

    async def send_json(self, payload):
        self.sent_payloads.append(payload)


def test_employee_websocket_rejects_invalid_token(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/me/courses/ws?token=bad-token"):
            pass


def test_employee_websocket_sends_initial_course_payload(
    client,
    active_employees,
    assigned_seed_courses,
):
    token, _employee = login_employee(client, active_employees[0]["id"])

    with client.websocket_connect(f"/api/me/courses/ws?token={token}") as websocket:
        payload = websocket.receive_json()

    assert len(payload) == 1
    assert payload[0]["course_id"] == assigned_seed_courses["published"]["course_id"]
    assert payload[0]["employee_status"] == "pending"


def test_employee_websocket_broadcast_is_employee_scoped(
    client,
    employee_routes,
    active_employees,
    assigned_seed_courses,
):
    course_id = assigned_seed_courses["published"]["course_id"]
    token_a, employee_a = login_employee(client, active_employees[0]["id"])
    _token_b, employee_b = login_employee(client, active_employees[1]["id"])
    socket_a_1 = FakeWebSocket()
    socket_a_2 = FakeWebSocket()
    socket_b = FakeWebSocket()
    employee_routes._active_websockets[employee_a["id"]] = [socket_a_1, socket_a_2]
    employee_routes._active_websockets[employee_b["id"]] = [socket_b]

    response = client.put(
        f"/api/me/courses/{course_id}/status",
        headers=auth_headers(token_a),
        json={"status": "started"},
    )

    assert response.status_code == 200
    assert len(socket_a_1.sent_payloads) == 1
    assert len(socket_a_2.sent_payloads) == 1
    assert socket_a_1.sent_payloads[0][0]["employee_status"] == "started"
    assert socket_a_2.sent_payloads[0][0]["employee_status"] == "started"
    assert socket_b.sent_payloads == []
