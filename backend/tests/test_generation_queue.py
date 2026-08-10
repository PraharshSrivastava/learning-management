from __future__ import annotations

from threading import Thread

from app.services.generation_queue import GenerationQueue


def test_generation_queue_continues_after_failed_item() -> None:
    queue = GenerationQueue()
    tickets = [
        queue.enqueue(course_id="course_1", operation="blueprint"),
        queue.enqueue(course_id="course_2", operation="full_course"),
        queue.enqueue(course_id="course_3", operation="quiz"),
    ]
    order: list[str] = []
    failures: list[str] = []

    def run_ticket(index: int) -> None:
        try:
            with queue.run_ticket(tickets[index]):
                order.append(tickets[index].course_id)
                if index == 0:
                    raise RuntimeError("first failed")
        except RuntimeError as exc:
            failures.append(str(exc))

    threads = [Thread(target=run_ticket, args=(index,)) for index in range(len(tickets))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert order == ["course_1", "course_2", "course_3"]
    assert failures == ["first failed"]
    assert queue.snapshot()["active"] is None
    assert queue.snapshot()["pending"] == []


def test_generation_queue_stop_releases_waiting_ticket() -> None:
    queue = GenerationQueue()
    ticket = queue.enqueue(course_id="course_1", operation="blueprint")
    queue.stop()

    try:
        queue.wait_for_turn(ticket)
    except RuntimeError as exc:
        assert str(exc) == "Generation queue is stopped"
    else:
        raise AssertionError("Expected stopped queue to reject waiting ticket")
