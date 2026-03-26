"""
In-memory job store for tracking async generation jobs.
Fine for v1/v2 (single process). Replace with Redis in v3.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator


MAX_JOBS = 20
JOB_TTL_SECONDS = 30 * 60  # 30 minutes


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
    created_at: float = field(default_factory=time.monotonic)

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


def create_job(job_id: str) -> Job | None:
    """Create a new job. Returns None if at capacity."""
    if len(_jobs) >= MAX_JOBS:
        return None
    job = Job(job_id=job_id)
    _jobs[job_id] = job
    return job


def get_job(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def cleanup_stale_jobs() -> int:
    """Remove jobs older than JOB_TTL_SECONDS. Returns count of evicted jobs."""
    now = time.monotonic()
    stale_ids = [
        job_id
        for job_id, job in _jobs.items()
        if (now - job.created_at) > JOB_TTL_SECONDS
    ]
    for job_id in stale_ids:
        del _jobs[job_id]
    return len(stale_ids)
