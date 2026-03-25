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
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

load_dotenv()

from job_store import JobEvent, JobStatus, create_job, get_job  # noqa: E402

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Paper → Notebook Generator", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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
async def generate(
    background_tasks: BackgroundTasks,
    api_key: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    """
    Accept a research paper PDF and an OpenAI API key.
    Returns a job_id immediately; client polls /stream/{job_id} for progress.
    The API key is forwarded only to OpenAI and never stored.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    pdf_bytes = await file.read()
    job_id = str(uuid.uuid4())
    job = create_job(job_id)

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
        notebook_node, summary_bullets = await generate_notebook(paper, api_key, progress)

        await progress("Assembling notebook structure...")
        import nbformat
        notebook_json = nbformat.writes(notebook_node)
        notebook_b64 = base64.b64encode(notebook_json.encode()).decode()

        await progress("Publishing to GitHub Gist for Colab link...")
        from gist_publisher import publish_to_gist
        colab_url = publish_to_gist(notebook_json, paper.get("title", "Research Paper Notebook"))

        job.status = JobStatus.DONE
        await job.push(JobEvent(
            type="done",
            message=json.dumps(summary_bullets),
            elapsed=round(time.monotonic() - start, 1),
            notebook_b64=notebook_b64,
            colab_url=colab_url,
        ))

    except Exception as exc:
        job.status = JobStatus.ERROR
        await job.push(JobEvent(
            type="error",
            message=str(exc),
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
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# POST /publish — create Gist on demand (called from frontend if needed)
# ---------------------------------------------------------------------------

@app.post("/publish")
async def publish(
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
