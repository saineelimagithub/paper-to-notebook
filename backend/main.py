"""
Paper → Notebook Generator — FastAPI Backend
"""
from __future__ import annotations

import asyncio
import base64
import json
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, Header, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

load_dotenv()

from job_store import JobEvent, JobStatus, create_job, get_job, cleanup_stale_jobs  # noqa: E402

limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

async def _periodic_cleanup():
    """Background task that evicts stale jobs every 60 seconds."""
    while True:
        await asyncio.sleep(60)
        cleanup_stale_jobs()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_periodic_cleanup())
    yield
    task.cancel()


app = FastAPI(title="Paper → Notebook Generator", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded. Try again in {exc.detail} seconds."},
    )


# ---------------------------------------------------------------------------
# Security Headers Middleware
# ---------------------------------------------------------------------------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Content-Type", "X-Api-Key"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /generate — accept PDF + API key, start async job
# ---------------------------------------------------------------------------

@app.post("/generate")
@limiter.limit("5/minute")
async def generate(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    x_api_key: str = Header(..., alias="X-Api-Key"),
) -> dict:
    """
    Accept a research paper PDF and a Gemini API key (via X-Api-Key header).
    Returns a job_id immediately; client polls /stream/{job_id} for progress.
    The API key is forwarded only to Gemini and never stored.
    """
    api_key = x_api_key
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    MAX_PDF_SIZE = 20 * 1024 * 1024  # 20 MB
    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_PDF_SIZE:
        raise HTTPException(status_code=413, detail="PDF exceeds 20MB limit.")
    job_id = str(uuid.uuid4())
    job = create_job(job_id)
    if job is None:
        raise HTTPException(status_code=503, detail="Server busy. Try again shortly.")

    background_tasks.add_task(_run_generation, job_id, pdf_bytes, api_key)

    return {"job_id": job_id}


async def _run_generation(job_id: str, pdf_bytes: bytes, api_key: str) -> None:
    """Background task: parse PDF → generate notebook → push SSE events."""
    import time

    job = get_job(job_id)
    if job is None:
        return

    job.status = JobStatus.RUNNING
    start = time.monotonic()

    async def progress(msg: str) -> None:
        elapsed = round(time.monotonic() - start, 1)
        await job.push(JobEvent(type="progress", message=msg, elapsed=elapsed))

    try:
        await progress("Parsing PDF structure and extracting text...")
        from pdf_parser import parse_pdf
        paper = parse_pdf(pdf_bytes)

        await progress(f"Identified paper type. Title: {paper.get('title', 'Unknown')[:80]}")
        await progress("Analyzing core algorithms and theoretical contributions...")

        from notebook_generator import generate_notebook
        notebook_node, summary_bullets, findings = await generate_notebook(paper, api_key, progress)

        await progress("Assembling notebook structure...")
        import nbformat
        notebook_json = nbformat.writes(notebook_node)
        notebook_b64 = base64.b64encode(notebook_json.encode()).decode()

        await progress("Publishing to GitHub Gist for Colab link...")
        from gist_publisher import publish_to_gist
        colab_url = publish_to_gist(notebook_json, paper.get("title", "Research Paper Notebook"))

        if findings:
            await progress(f"Security scan: {len(findings)} finding(s) detected in generated code.")

        job.status = JobStatus.DONE
        await job.push(JobEvent(
            type="done",
            message=json.dumps(summary_bullets),
            elapsed=round(time.monotonic() - start, 1),
            notebook_b64=notebook_b64,
            colab_url=colab_url,
            findings=findings,
        ))

    except Exception as exc:
        from error_handler import safe_error_message
        job.status = JobStatus.ERROR
        await job.push(JobEvent(
            type="error",
            message=safe_error_message(exc),
            elapsed=round(time.monotonic() - start, 1),
        ))


# ---------------------------------------------------------------------------
# GET /stream/{job_id} — Server-Sent Events
# ---------------------------------------------------------------------------

@app.get("/stream/{job_id}")
async def stream_job(job_id: str) -> StreamingResponse:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    async def event_generator():
        async for event in job.stream():
            payload = {
                "type": event.type,
                "message": event.message,
                "elapsed": event.elapsed,
            }
            if event.type == "done":
                payload["notebook_b64"] = event.notebook_b64
                payload["colab_url"] = event.colab_url
                payload["findings"] = event.findings
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# POST /publish — create Gist on demand (called from frontend if needed)
# ---------------------------------------------------------------------------

@app.post("/publish")
@limiter.limit("10/minute")
async def publish(
    request: Request,
    notebook_b64: str = Form(...),
    title: str = Form(...),
) -> dict:
    """Publish a base64-encoded notebook to GitHub Gist and return Colab URL."""
    from gist_publisher import publish_to_gist

    notebook_json = base64.b64decode(notebook_b64).decode()
    colab_url = publish_to_gist(notebook_json, title)
    if colab_url is None:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN not configured on server.")
    return {"colab_url": colab_url}
