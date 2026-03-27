"""
Unit tests for job_store — Job, JobEvent, create_job, get_job, push/stream.
Run: cd backend && python -m pytest ../tests/backend/test_job_store.py -v
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

import pytest
from job_store import (
    Job, JobEvent, JobStatus,
    create_job, get_job, _jobs,
    MAX_JOBS, JOB_TTL_SECONDS,
)


def setup_function():
    """Clear job store before each test."""
    _jobs.clear()


# ─────────────────────────────────────────────────────────────────────────────
# JobEvent
# ─────────────────────────────────────────────────────────────────────────────


def test_job_event_defaults():
    """JobEvent should have sensible defaults."""
    event = JobEvent(type="progress")
    assert event.type == "progress"
    assert event.message == ""
    assert event.elapsed == 0.0
    assert event.notebook_b64 == ""
    assert event.colab_url is None
    assert event.findings == []


def test_job_event_findings_field():
    """JobEvent findings field should accept a list of dicts."""
    findings = [{"cell_index": 0, "pattern": "eval", "severity": "critical"}]
    event = JobEvent(type="done", findings=findings)
    assert event.findings == findings
    assert len(event.findings) == 1


def test_job_event_done_with_all_fields():
    """JobEvent can carry all fields for a done event."""
    event = JobEvent(
        type="done",
        message="success",
        elapsed=12.5,
        notebook_b64="YWJj",
        colab_url="https://colab.example.com",
        findings=[],
    )
    assert event.notebook_b64 == "YWJj"
    assert event.colab_url == "https://colab.example.com"


# ─────────────────────────────────────────────────────────────────────────────
# JobStatus
# ─────────────────────────────────────────────────────────────────────────────


def test_job_status_values():
    """JobStatus should have the expected enum values."""
    assert JobStatus.PENDING == "pending"
    assert JobStatus.RUNNING == "running"
    assert JobStatus.DONE == "done"
    assert JobStatus.ERROR == "error"


# ─────────────────────────────────────────────────────────────────────────────
# Job
# ─────────────────────────────────────────────────────────────────────────────


def test_job_initial_state():
    """New Job should be PENDING with empty events."""
    job = Job(job_id="test-1")
    assert job.job_id == "test-1"
    assert job.status == JobStatus.PENDING
    assert job.events == []
    assert isinstance(job.created_at, float)


@pytest.mark.asyncio
async def test_job_push_adds_event():
    """Job.push() should add event to events list."""
    job = Job(job_id="test-1")
    event = JobEvent(type="progress", message="parsing")
    await job.push(event)
    assert len(job.events) == 1
    assert job.events[0].message == "parsing"


@pytest.mark.asyncio
async def test_job_push_stream_roundtrip():
    """Events pushed should be receivable via stream()."""
    job = Job(job_id="test-1")

    # Push a progress event then a done event
    await job.push(JobEvent(type="progress", message="step 1"))
    await job.push(JobEvent(type="done", message="finished"))

    received = []
    async for event in job.stream():
        received.append(event)

    assert len(received) == 2
    assert received[0].type == "progress"
    assert received[1].type == "done"


@pytest.mark.asyncio
async def test_job_stream_stops_on_done():
    """stream() should stop yielding after a done event."""
    job = Job(job_id="test-1")
    await job.push(JobEvent(type="progress", message="working"))
    await job.push(JobEvent(type="done", message="complete"))

    count = 0
    async for _ in job.stream():
        count += 1

    assert count == 2  # progress + done, then stops


@pytest.mark.asyncio
async def test_job_stream_stops_on_error():
    """stream() should stop yielding after an error event."""
    job = Job(job_id="test-1")
    await job.push(JobEvent(type="error", message="failed"))

    received = []
    async for event in job.stream():
        received.append(event)

    assert len(received) == 1
    assert received[0].type == "error"


# ─────────────────────────────────────────────────────────────────────────────
# create_job / get_job
# ─────────────────────────────────────────────────────────────────────────────


def test_create_job_returns_job():
    """create_job() should return a Job instance."""
    job = create_job("abc-123")
    assert isinstance(job, Job)
    assert job.job_id == "abc-123"


def test_get_job_returns_created_job():
    """get_job() should return a previously created job."""
    create_job("abc-123")
    job = get_job("abc-123")
    assert job is not None
    assert job.job_id == "abc-123"


def test_get_job_returns_none_for_unknown():
    """get_job() should return None for unknown job_id."""
    result = get_job("nonexistent-id")
    assert result is None


def test_create_job_returns_none_at_capacity():
    """create_job() should return None when at MAX_JOBS."""
    for i in range(MAX_JOBS):
        create_job(f"job-{i}")
    result = create_job("one-too-many")
    assert result is None


def test_constants():
    """MAX_JOBS and JOB_TTL_SECONDS should have expected values."""
    assert MAX_JOBS == 20
    assert JOB_TTL_SECONDS == 1800  # 30 minutes
