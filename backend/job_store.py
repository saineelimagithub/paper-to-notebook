"""
In-memory job store for tracking async generation jobs.
Fine for v1 (single process). Replace with Redis in v2.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class JobEvent:
    type: str  # "progress" | "done" | "error"
    message: str = ""
    elapsed: float = 0.0
    notebook_b64: str = ""
    colab_url: str | None = None
    findings: list = field(default_factory=list)


@dataclass
class Job:
    job_id: str
    status: JobStatus = JobStatus.PENDING
    events: list[JobEvent] = field(default_factory=list)
    _queue: asyncio.Queue = field(default_factory=asyncio.Queue)

    async def push(self, event: JobEvent) -> None:
        self.events.append(event)
        await self._queue.put(event)

    async def stream(self) -> AsyncGenerator[JobEvent, None]:
        """Yield events as they arrive; stops when done/error is received."""
        while True:
            event = await self._queue.get()
            yield event
            if event.type in ("done", "error"):
                break


# Global store — keyed by job_id
_jobs: dict[str, Job] = {}


def create_job(job_id: str) -> Job:
    job = Job(job_id=job_id)
    _jobs[job_id] = job
    return job


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)
