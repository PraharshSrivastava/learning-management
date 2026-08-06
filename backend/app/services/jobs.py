"""Bounded job manager with durable state and optional subprocess execution."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Callable
from uuid import uuid4

from app.repositories.jobs import GenerationJobRepository
from app.schemas.generation import GenerationJobResponse


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GenerationJobManager:
    def __init__(
        self,
        max_workers: int = 1,
        repository: GenerationJobRepository | None = None,
    ):
        self._max_workers = max_workers
        self._executor: ThreadPoolExecutor | None = None
        self._repository = repository
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._jobs: dict[str, GenerationJobResponse] = {}
        self._active_course_jobs: set[str] = set()
        self._lock = Lock()

    def submit(self, course_id: str, operation: Callable[[], object]) -> GenerationJobResponse:
        """Run a callable in the bounded monitor pool.

        This remains useful for tests and lightweight local operations. Production
        course generation uses :meth:`submit_process`, which runs the pipeline in
        a separate Python process.
        """
        with self._lock:
            job = self._create_job(course_id)
            executor = self._executor_for_submit()
        executor.submit(self._run, job.id, operation)
        return job

    def submit_process(
        self,
        course_id: str,
        *,
        backend_dir: Path,
        restart_from_blueprint: bool,
    ) -> GenerationJobResponse:
        command = [
            sys.executable,
            "-m",
            "scripts.run_pipeline",
            "--course-id",
            course_id,
        ]
        if restart_from_blueprint:
            command.append("--restart-from-blueprint")

        with self._lock:
            job = self._create_job(course_id)
            executor = self._executor_for_submit()

        def operation() -> None:
            popen_kwargs = {
                "cwd": str(backend_dir),
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
            }
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                popen_kwargs["start_new_session"] = True
            with self._lock:
                process = subprocess.Popen(
                    command,
                    **popen_kwargs,
                )
                self._processes[job.id] = process
            try:
                stdout, stderr = process.communicate()
            finally:
                with self._lock:
                    self._processes.pop(job.id, None)
            if process.returncode:
                detail = (stderr or stdout or "").strip()
                raise RuntimeError(
                    detail or f"Pipeline process exited with code {process.returncode}"
                )

        executor.submit(self._run, job.id, operation)
        return job

    def get(self, job_id: str) -> GenerationJobResponse | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                return job.model_copy(deep=True)
        return self._repository.get(job_id) if self._repository else None

    def shutdown(self) -> None:
        """Cancel queued monitors and terminate active pipeline subprocesses."""
        with self._lock:
            executor = self._executor
            self._executor = None
            processes = list(self._processes.values())
        for process in processes:
            self._terminate_process(process)
        if executor:
            executor.shutdown(wait=True, cancel_futures=True)

    def recover_interrupted(self) -> int:
        if not self._repository:
            return 0
        return self._repository.fail_interrupted(
            "Generation worker was interrupted by an API process restart."
        )

    def _executor_for_submit(self) -> ThreadPoolExecutor:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="generation-monitor",
            )
        return self._executor

    def _create_job(self, course_id: str) -> GenerationJobResponse:
        """Create a job while the caller holds ``self._lock``."""
        if course_id in self._active_course_jobs:
            raise ValueError("Generation is already running for this course")
        job = GenerationJobResponse(
            id=str(uuid4()),
            course_id=course_id,
            status="pending",
            created_at=_now(),
        )
        if self._repository:
            self._repository.create(job)
        self._jobs[job.id] = job
        self._active_course_jobs.add(course_id)
        return job

    @staticmethod
    def _terminate_process(process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            try:
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
            return
        except subprocess.TimeoutExpired:
            pass
        except OSError:
            return
        try:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def _save(self, job: GenerationJobResponse) -> None:
        if self._repository:
            self._repository.save(job)

    def _run(self, job_id: str, operation: Callable[[], object]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "running"
            job.started_at = _now()
            self._save(job)
        try:
            operation()
        except Exception as exc:
            with self._lock:
                job.status = "failed"
                job.error = str(exc)
                job.completed_at = _now()
                self._save(job)
        else:
            with self._lock:
                job.status = "completed"
                job.completed_at = _now()
                self._save(job)
        finally:
            with self._lock:
                self._active_course_jobs.discard(job.course_id)
