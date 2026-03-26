"""
Job cleanup and cap tests — verifies TTL eviction and max concurrent job limits.
Run: cd backend && python -m pytest ../tests/backend/test_job_cleanup.py -v
"""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from job_store import Job, JobStatus, create_job, get_job, _jobs, cleanup_stale_jobs, MAX_JOBS, JOB_TTL_SECONDS


def setup_function():
    """Clear job store before each test."""
    _jobs.clear()


def test_create_job_has_created_at():
    job = create_job("test-1")
    assert hasattr(job, "created_at")
    assert isinstance(job.created_at, float)


def test_cleanup_removes_old_jobs(monkeypatch):
    """Jobs older than TTL should be evicted."""
    job = create_job("old-job")
    # Simulate old job by backdating created_at
    job.created_at = time.monotonic() - JOB_TTL_SECONDS - 10
    job.status = JobStatus.DONE

    cleanup_stale_jobs()

    assert get_job("old-job") is None
    assert "old-job" not in _jobs


def test_cleanup_keeps_recent_jobs():
    """Recent jobs should not be evicted."""
    job = create_job("new-job")
    job.status = JobStatus.RUNNING

    cleanup_stale_jobs()

    assert get_job("new-job") is not None


def test_cleanup_keeps_active_recent_jobs():
    """Active (RUNNING) recent jobs must not be evicted."""
    job = create_job("active-job")
    job.status = JobStatus.RUNNING

    cleanup_stale_jobs()

    assert get_job("active-job") is not None


def test_max_jobs_cap():
    """Creating more than MAX_JOBS should fail."""
    for i in range(MAX_JOBS):
        create_job(f"job-{i}")

    assert len(_jobs) == MAX_JOBS

    # Next one should return None (at capacity)
    result = create_job(f"job-{MAX_JOBS}")
    assert result is None


def test_under_cap_succeeds():
    """Creating jobs under the cap should succeed."""
    job = create_job("first-job")
    assert job is not None
    assert job.job_id == "first-job"


def test_cleanup_frees_slots_for_new_jobs():
    """After cleanup evicts old jobs, new ones can be created."""
    # Fill up to cap
    for i in range(MAX_JOBS):
        j = create_job(f"job-{i}")
        j.created_at = time.monotonic() - JOB_TTL_SECONDS - 10
        j.status = JobStatus.DONE

    # Can't create more
    assert create_job("blocked") is None

    # Cleanup
    cleanup_stale_jobs()

    # Now we can create again
    new_job = create_job("fresh-job")
    assert new_job is not None
