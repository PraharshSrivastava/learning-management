"""Process-local FIFO queue for generation work.

The queue intentionally lives in memory: if the backend process stops, queued
items stop with it. Persisted course generation state remains responsible for
recovering an interrupted running course.
"""

from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Condition
from uuid import uuid4


@dataclass(frozen=True)
class GenerationQueueTicket:
    id: str
    course_id: str
    operation: str


class GenerationQueue:
    def __init__(self) -> None:
        self._condition = Condition()
        self._pending: deque[GenerationQueueTicket] = deque()
        self._active: GenerationQueueTicket | None = None
        self._stopped = False

    @contextmanager
    def run(self, *, course_id: str, operation: str):
        ticket = self.enqueue(course_id=course_id, operation=operation)
        with self.run_ticket(ticket):
            yield ticket

    @contextmanager
    def run_ticket(self, ticket: GenerationQueueTicket):
        self.wait_for_turn(ticket)
        try:
            yield ticket
        finally:
            self.complete(ticket)

    def enqueue(self, *, course_id: str, operation: str) -> GenerationQueueTicket:
        ticket = GenerationQueueTicket(
            id=str(uuid4()),
            course_id=course_id,
            operation=operation,
        )
        with self._condition:
            if self._stopped:
                raise RuntimeError("Generation queue is stopped")
            self._pending.append(ticket)
            self._condition.notify_all()
        return ticket

    def wait_for_turn(self, ticket: GenerationQueueTicket) -> None:
        with self._condition:
            self._condition.wait_for(
                lambda: self._stopped
                or (
                    self._active is None
                    and bool(self._pending)
                    and self._pending[0].id == ticket.id
                )
            )
            if self._stopped:
                self._pending = deque(item for item in self._pending if item.id != ticket.id)
                raise RuntimeError("Generation queue is stopped")
            self._active = self._pending.popleft()
            self._condition.notify_all()

    def complete(self, ticket: GenerationQueueTicket) -> None:
        with self._condition:
            if self._active and self._active.id == ticket.id:
                self._active = None
            else:
                self._pending = deque(item for item in self._pending if item.id != ticket.id)
            self._condition.notify_all()

    def clear(self) -> None:
        with self._condition:
            self._pending.clear()
            self._active = None
            self._condition.notify_all()

    def start(self) -> None:
        with self._condition:
            self._stopped = False
            self._condition.notify_all()

    def stop(self) -> None:
        with self._condition:
            self._stopped = True
            self._pending.clear()
            self._active = None
            self._condition.notify_all()

    def snapshot(self) -> dict:
        with self._condition:
            return {
                "active": self._active,
                "pending": list(self._pending),
            }


generation_queue = GenerationQueue()
