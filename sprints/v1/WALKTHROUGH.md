# Sprint v1 — Walkthrough

## Summary

Built a full-stack web application that converts research paper PDFs into production-quality Google Colab notebooks. A researcher uploads a paper, enters their OpenAI API key, and receives a downloadable `.ipynb` file containing a 10-section tutorial — with working algorithm implementations, realistic synthetic data, experiments, visualizations, and an ablation study. The backend uses FastAPI with Server-Sent Events for real-time progress streaming; the frontend is a React SPA styled after arcprize.org's dark, minimal aesthetic. An optional "Open in Colab" feature publishes notebooks as GitHub Gists.

**46 backend tests + 12 Playwright E2E tests. 0 semgrep findings. 0 npm audit vulnerabilities.**

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Browser (React + Vite)                        │
│                          localhost:5173                               │
│                                                                      │
│  State Machine: idle → processing → done | error                     │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │ APIKeyInput  │  │ PDFUpload    │  │ Progress    │  │ Result   │ │
│  │ (password    │  │ (drag+drop   │  │ Display     │  │ Card     │ │
│  │  show/hide)  │  │  + browse)   │  │ (SSE log)   │  │ (DL+Colab│ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘  └────┬─────┘ │
│         │                 │                  │              │        │
│         └────── idle ─────┘     processing ──┘    done ─────┘        │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                    POST /generate (multipart: api_key + pdf)
                    GET  /stream/{job_id} (SSE)
                    POST /publish (on-demand Gist creation)
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend (Python)                          │
│                        localhost:8000                                 │
│                                                                      │
│  ┌──────────┐    ┌─────────────┐    ┌────────────┐    ┌───────────┐ │
│  │ main.py  │───▶│ pdf_parser  │───▶│ notebook   │───▶│ gist      │ │
│  │ (routes) │    │  .py        │    │ _generator │    │ _publisher│ │
│  └──────────┘    │             │    │   .py      │    │   .py     │ │
│       │          │ PyMuPDF     │    │ OpenAI API │    │ GitHub API│ │
│       │          │ (fitz)      │    │ + nbformat │    │ (httpx)   │ │
│       ▼          └─────────────┘    └────────────┘    └───────────┘ │
│  ┌──────────┐                                                        │
│  │job_store │  In-memory async queue for SSE event streaming         │
│  │  .py     │  (dict[job_id] → Job with asyncio.Queue)               │
│  └──────────┘                                                        │
└──────────────────────────────────────────────────────────────────────┘
```

## Files Created/Modified

---

### `backend/main.py`
**Purpose**: FastAPI application with all HTTP endpoints — the API surface of the entire backend.

**Key Functions/Endpoints**:
- `GET /health` — Returns `{"status": "ok"}`. Used by monitoring and tests to verify the server is running.
- `POST /generate` — Accepts `multipart/form-data` with `api_key` (string) and `file` (PDF upload). Validates that the file is a PDF, creates a job in the in-memory store, launches background processing, and immediately returns `{"job_id": "..."}`.
- `GET /stream/{job_id}` — Server-Sent Events endpoint. Opens a long-lived connection and yields JSON events (`progress`, `done`, `error`) as the background task runs. The frontend's `EventSource` consumes this.
- `POST /publish` — On-demand Gist creation. Accepts a base64-encoded notebook + title, publishes to GitHub Gist, returns a Colab URL.
- `_run_generation()` — The background task that orchestrates the full pipeline: parse PDF → call GPT-4o → build notebook → publish Gist → push SSE events.

**How it works**:
When the user clicks "Generate Notebook", the frontend POSTs the PDF and API key to `/generate`. The endpoint reads the PDF bytes, generates a UUID job ID, stores a `Job` object in the in-memory store, and schedules `_run_generation()` as a FastAPI background task. The response returns the `job_id` immediately (< 100ms).

The frontend then opens an `EventSource` connection to `/stream/{job_id}`. The background task pushes `JobEvent` objects through an `asyncio.Queue` on the `Job`, and the SSE endpoint yields them as `data: {...}\n\n` lines. Each event has a `type` (progress/done/error), a `message`, and an `elapsed` timer in seconds. The `done` event includes the full notebook as a base64-encoded string and an optional Colab URL.

CORS is configured to allow requests from `localhost:5173` and `127.0.0.1:5173` — the Vite dev server origins. The API key is passed through to OpenAI and never logged, stored, or returned in any response.

```python
@app.post("/generate")
async def generate(
    background_tasks: BackgroundTasks,
    api_key: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")
    pdf_bytes = await file.read()
    job_id = str(uuid.uuid4())
    job = create_job(job_id)
    background_tasks.add_task(_run_generation, job_id, pdf_bytes, api_key)
    return {"job_id": job_id}
```

---

### `backend/job_store.py`
**Purpose**: In-memory job state manager with async event queuing for SSE streaming.

**Key Types**:
- `JobStatus` — Enum: `PENDING`, `RUNNING`, `DONE`, `ERROR`
- `JobEvent` — Dataclass: `type`, `message`, `elapsed`, `notebook_b64`, `colab_url`
- `Job` — Dataclass with an `asyncio.Queue` for push/stream pattern:
  - `push(event)` — Appends to history list and puts on the queue
  - `stream()` — Async generator that yields events from the queue until a terminal event (`done`/`error`)
- `create_job(job_id)` / `get_job(job_id)` — Module-level dict operations

**How it works**:
Each generation request creates a `Job` with a unique ID stored in a module-level `dict`. The background task calls `job.push()` to emit events, and the SSE endpoint iterates `job.stream()`. The `asyncio.Queue` ensures the SSE endpoint blocks efficiently (no polling) until new events arrive. When a `done` or `error` event is received, the stream terminates.

This is intentionally simple — a single-process in-memory store. If the server restarts, all job state is lost. For v2, this should be replaced with Redis or a similar persistent queue.

```python
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
        while True:
            event = await self._queue.get()
            yield event
            if event.type in ("done", "error"):
                break
```

---

### `backend/pdf_parser.py`
**Purpose**: Extracts structured content (title, abstract, sections, full text) from research paper PDFs using PyMuPDF.

**Key Functions**:
- `parse_pdf(pdf_bytes) -> dict` — Main entry point. Returns `{"title", "abstract", "sections", "full_text"}`.
- `_extract_title(doc)` — Finds the largest-font text on page 1 (typically the paper title). Falls back to the first bold or first non-empty line.
- `_extract_structure(full_text)` — Splits the full text into abstract + section list by detecting heading patterns.
- `_is_section_heading(line)` — Regex + heuristic matching for numbered sections (`1. Introduction`), common academic headings (`Related Work`, `Methodology`, etc.), ALL CAPS lines, and Title Case lines.

**How it works**:
The parser opens the PDF from raw bytes using `fitz.open(stream=..., filetype="pdf")`. For title extraction, it uses PyMuPDF's `get_text("dict")` to access span-level font metadata on page 1 and picks the span(s) with the maximum font size. If the result is too short (< 4 chars), it falls back to the next largest size.

For abstract extraction, it scans lines for a case-insensitive match on `^\s*abstract\s*$`, then collects body lines until the next section heading. Section detection uses a compiled regex for common academic heading patterns, plus heuristics for ALL CAPS lines and Title Case short phrases.

All errors are caught and return an empty-result dict — the parser never crashes, even on corrupt or empty input.

```python
def _extract_title(doc: fitz.Document) -> str:
    page = doc[0]
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    candidates = []
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "").strip()
                size = span.get("size", 0)
                if text:
                    candidates.append((size, text))
    max_size = max(c[0] for c in candidates)
    title_parts = [text for size, text in candidates if size == max_size]
    return " ".join(title_parts).strip()
```

---

### `backend/notebook_generator.py`
**Purpose**: The core intelligence — calls GPT-4o with a detailed system prompt to analyze a research paper and generate a 10-section Colab notebook, then assembles it into a valid `.ipynb` using `nbformat`.

**Key Functions**:
- `generate_notebook(paper, api_key, progress)` — Async function that calls OpenAI's API and returns `(NotebookNode, summary_bullets)`.
- `build_notebook(cells)` — Takes a list of `{"type": "markdown"|"code", "source": str}` dicts and assembles them into a valid `nbformat.v4` NotebookNode with Colab-specific metadata.
- `SYSTEM_PROMPT` — 94-line prompt that instructs GPT-4o to produce a JSON response with exactly 10 sections.

**How it works**:
The function constructs a user message containing the paper's title, abstract, and the first 12,000 characters of the full text (to fit within token limits). It sends this to GPT-4o with `response_format={"type": "json_object"}` and `temperature=0.2` for deterministic output.

The system prompt is the most critical piece of the entire application. It specifies the exact 10-section structure: Title & Overview → Installation & Setup → Theoretical Background → Algorithm Pseudocode → Core Implementation → Synthetic Dataset → Experiments → Visualization → Ablation Study → Summary. Key quality requirements are explicitly stated: type hints, docstrings, realistic synthetic data at scale (1000-10000 samples), publication-quality plots, LaTeX equations, and baseline comparisons.

The response is parsed as JSON, and `build_notebook()` converts each cell dict into nbformat cells. The notebook metadata includes `kernelspec` (Python 3), `language_info`, and `colab` settings (provenance, TOC visible). The notebook is validated with `nbformat.validate()` before returning.

```python
response = await client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ],
    response_format={"type": "json_object"},
    max_tokens=8000,
    temperature=0.2,
)
result = json.loads(response.choices[0].message.content)
notebook = build_notebook(result["cells"])
summary_bullets = result.get("summary_bullets", [])
```

---

### `backend/gist_publisher.py`
**Purpose**: Publishes a generated notebook as a public GitHub Gist and returns a Google Colab URL.

**Key Functions**:
- `publish_to_gist(notebook_json, title) -> str | None` — Creates a Gist via the GitHub API and returns `https://colab.research.google.com/gist/{username}/{gist_id}`. Returns `None` if no `GITHUB_TOKEN` is configured.

**How it works**:
The function reads `GITHUB_TOKEN` from environment variables. If absent, it returns `None` — the frontend gracefully hides the "Open in Colab" button and shows only the download option.

When a token is available, it sanitizes the paper title into a safe filename (alphanumeric + space/hyphen/underscore, truncated to 80 characters), creates a Gist payload with the notebook JSON as file content, and POSTs to `api.github.com/gists` using the GitHub API v2022-11-28 headers with Bearer token authentication.

The response contains the `gist_id` and `owner.login`, which are combined into a Colab URL. Google Colab natively supports opening notebooks from GitHub Gists via this URL pattern.

```python
def publish_to_gist(notebook_json: str, title: str) -> str | None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)[:80]
    filename = f"{safe_title}.ipynb"
    # ... POST to api.github.com/gists ...
    return f"https://colab.research.google.com/gist/{owner_login}/{gist_id}"
```

---

### `backend/requirements.txt`
**Purpose**: Python dependency manifest.

**Packages**:
- `fastapi==0.135.2` — Web framework (upgraded from 0.115.6 to fix starlette CVEs)
- `uvicorn[standard]==0.32.1` — ASGI server
- `python-multipart==0.0.22` — File upload parsing (upgraded from 0.0.20 to fix CVE-2026-24486)
- `pymupdf==1.25.1` — PDF text extraction
- `openai==1.59.3` — OpenAI API client
- `nbformat==5.10.4` — Jupyter notebook format library
- `httpx==0.28.1` — HTTP client for GitHub Gist API
- `python-dotenv==1.0.1` — `.env` file loading
- `pytest==8.3.4` — Testing framework

---

### `backend/.env.example`
**Purpose**: Template for server-side environment variables. Copy to `.env` and fill in values.

Contains one variable: `GITHUB_TOKEN` — a GitHub Personal Access Token with `gist` scope, required for the "Open in Colab" feature. If not set, the app still works in download-only mode.

---

### `frontend/src/App.jsx`
**Purpose**: Top-level React component implementing the application state machine.

**State Machine**: `idle → processing → done | error`

**State Variables**:
- `apiKey` — User's OpenAI API key (never leaves React state)
- `appState` — Current state: `"idle"`, `"processing"`, `"done"`, `"error"`
- `jobId` — UUID returned by `/generate`, used for SSE connection
- `result` — `{ notebookB64, colabUrl, bullets }` — populated on `done`
- `errorMsg` — Error message string — populated on `error`

**How it works**:
The App component renders different children based on `appState`:
- **idle**: Shows `APIKeyInput` + `PDFUpload`. The user enters their key and selects a PDF.
- **processing**: Shows `ProgressDisplay` connected to the SSE stream.
- **done**: Shows `ResultCard` with download button + optional Colab link.
- **error**: Shows error message with a "Try Again" button.

On submit, `handleSubmit()` POSTs the FormData to `/generate`, transitions to "processing", and stores the `job_id`. The `ProgressDisplay` opens an `EventSource` to `/stream/{job_id}` and calls `handleDone()` when the terminal event arrives. `handleReset()` clears all state and returns to idle.

```jsx
const handleSubmit = async (formData) => {
  try {
    setAppState("processing");
    const res = await fetch("/generate", { method: "POST", body: formData });
    if (!res.ok) throw new Error(await res.text());
    const { job_id } = await res.json();
    setJobId(job_id);
  } catch (e) {
    setErrorMsg(e.message);
    setAppState("error");
  }
};
```

---

### `frontend/src/components/APIKeyInput.jsx`
**Purpose**: Password input field for the user's OpenAI API key with show/hide toggle.

**Props**: `value` (string), `onChange` (callback)

**How it works**:
Renders a password-type `<input>` with a "show/hide" toggle button. The key is stored only in the parent component's React state — never written to localStorage, cookies, or sent anywhere except as a form field in the `/generate` POST. A lock icon and text note ("Your key is never stored — used only for this session") provide user reassurance.

---

### `frontend/src/components/PDFUpload.jsx`
**Purpose**: Drag-and-drop file upload zone with submit button.

**Props**: `onSubmit` (callback), `apiKey` (string), `disabled` (boolean)

**How it works**:
A `<label>` element acts as the drop zone, handling `onDragOver`, `onDragLeave`, and `onDrop` events. The hidden `<input type="file" accept=".pdf">` handles click-to-browse. Both paths validate that the MIME type is `application/pdf`. Once a file is selected, the zone shows the filename and size (in MB).

The "Generate Notebook →" button is disabled until both `apiKey` and `file` are present. On click, it constructs a `FormData` with two fields (`api_key`, `file`) and calls `onSubmit()`.

```jsx
const canSubmit = !!file && !!apiKey && !disabled;
```

---

### `frontend/src/components/ProgressDisplay.jsx`
**Purpose**: Real-time progress log connected to the backend's SSE stream.

**Props**: `jobId` (string), `onDone` (callback), `onError` (callback)

**How it works**:
When `jobId` becomes truthy, a `useEffect` opens an `EventSource` to `/stream/{jobId}`. Each `progress` event is appended to the `messages` array with a formatted timestamp (`[MM:SS]`). A `useEffect` on `messages` auto-scrolls the log container to the bottom.

The display shows a status indicator: a pulsing green dot for connecting/running, a static green dot for complete, or a red dot for errors. The log window is styled as a terminal (monospace font, dark background, green timestamp accents).

When a `done` event arrives, the EventSource is closed and `onDone()` is called with the full event payload. On `error`, `onError()` is called with the message.

```jsx
es.onmessage = (e) => {
  const event = JSON.parse(e.data);
  if (event.type === "progress") {
    const mins = String(Math.floor(event.elapsed / 60)).padStart(2, "0");
    const secs = String(Math.floor(event.elapsed % 60)).padStart(2, "0");
    setMessages((prev) => [...prev, { ts: `${mins}:${secs}`, text: event.message }]);
    setStatus("running");
  } else if (event.type === "done") {
    setStatus("done");
    es.close();
    onDone(event);
  }
};
```

---

### `frontend/src/components/ResultCard.jsx`
**Purpose**: Success state UI showing download button, Colab link, summary bullets, and reset option.

**Props**: `title`, `bullets` (array), `notebookB64` (base64 string), `colabUrl` (string|null), `onReset` (callback)

**How it works**:
The download button decodes the base64 notebook into a Uint8Array via `atob()`, creates a Blob, generates an object URL, and triggers a download with a sanitized filename (`{title}_notebook.ipynb`). The object URL is revoked immediately after to prevent memory leaks.

The "Open in Colab ↗" button only appears if `colabUrl` is non-null. It opens the Colab URL in a new tab with `rel="noopener noreferrer"`.

Summary bullets (3 items from GPT-4o's response) are displayed as a list with green arrow prefixes. The "Generate Another →" button calls `onReset()` to return to the idle state.

```jsx
const handleDownload = () => {
  const bytes = atob(notebookB64);
  const arr = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
  const blob = new Blob([arr], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${safeName}_notebook.ipynb`;
  a.click();
  URL.revokeObjectURL(url);
};
```

---

### `frontend/src/index.css`
**Purpose**: Global CSS — Tailwind directives, base reset, typography, scrollbar styling, and custom utility classes.

**Key custom utilities**:
- `.text-gradient` — Linear gradient text (white → gray) used on the "→" arrow in the title
- `.border-subtle` — 1px `#2a2a2a` border
- `.glow-accent` — Soft green box shadow (`#4ade8020`) used on the result card and active generate button

Also includes custom scrollbar styling (6px width, dark track, subtle thumb) and `::selection` in green tint.

---

### `frontend/tailwind.config.js`
**Purpose**: Tailwind CSS configuration with the arcprize.org-inspired design system.

**Design Tokens**:
- `surface: #0d0d0d` — Primary background (near-black)
- `surface-1: #161616` — Card/panel background
- `surface-2: #1e1e1e` — Input background
- `border: #2a2a2a` — Subtle borders
- `text-primary: #e8e8e8` — Main text (off-white)
- `text-muted: #888888` — Secondary text
- `accent: #4ade80` — Green highlights (status, buttons, timestamps)
- `danger: #f87171` — Error states
- `font-sans: Inter` — Headings and body
- `font-mono: JetBrains Mono` — Code, labels, technical elements
- `max-w-content: 720px` — Centered single-column layout width

---

### `frontend/vite.config.js`
**Purpose**: Vite build configuration with API proxy to the FastAPI backend.

Proxies `/generate`, `/stream`, `/publish`, and `/health` to `http://localhost:8000`. This means in development, the frontend and backend can run on separate ports without CORS issues for API calls (CORS middleware is also configured as a fallback).

---

### `frontend/index.html`
**Purpose**: HTML entry point. Loads Google Fonts (Inter + JetBrains Mono) and mounts the React app to `#root`.

---

### `playwright.config.js`
**Purpose**: Playwright test configuration. Tests run against `http://localhost:5173` in headless Chromium. The Vite dev server auto-starts via the `webServer` config.

---

### `.gitignore`
**Purpose**: Excludes Python artifacts (`__pycache__`, `.venv`), Node artifacts (`node_modules`, `dist`), environment files (`.env`), test screenshots, and IDE files.

---

## Data Flow

```
1. User opens http://localhost:5173
   └── App renders in "idle" state: APIKeyInput + PDFUpload visible

2. User types their OpenAI API key
   └── Stored in React useState only (never persisted)

3. User drops or browses for a PDF file
   └── File validated client-side (must be application/pdf)
   └── "Generate Notebook →" button activates (green, glowing)

4. User clicks "Generate Notebook →"
   └── PDFUpload builds FormData: { api_key: "sk-...", file: paper.pdf }
   └── App.handleSubmit() → POST /generate → receives { job_id: "abc-123" }
   └── App transitions to "processing" state

5. ProgressDisplay mounts → opens EventSource(/stream/abc-123)
   └── Backend _run_generation() starts:
       ├── parse_pdf(bytes) → { title, abstract, sections, full_text }
       ├── SSE: "Parsing PDF structure and extracting text..."
       ├── SSE: "Identified paper type. Title: Attention Is All You Need"
       ├── generate_notebook(paper, api_key, progress)
       │   ├── SSE: "Analyzing core algorithms and theoretical contributions..."
       │   ├── SSE: "Mapping methodology to implementable components..."
       │   ├── → OpenAI gpt-4o API call (30-90 seconds)
       │   ├── SSE: "Assembling notebook cells..."
       │   └── returns (NotebookNode, ["bullet1", "bullet2", "bullet3"])
       ├── nbformat.writes(notebook) → JSON → base64 encode
       ├── publish_to_gist(json, title) → Colab URL (or None)
       └── SSE: { type: "done", notebook_b64: "...", colab_url: "https://..." }

6. ProgressDisplay receives "done" event → calls App.handleDone()
   └── App stores result, transitions to "done" state

7. ResultCard renders:
   ├── "Download .ipynb" → base64 decode → Blob → browser download
   ├── "Open in Colab ↗" → new tab to colab.research.google.com/gist/...
   └── "Generate Another →" → App.handleReset() → back to idle state
```

## Test Coverage

### Backend: 46 tests
- **Smoke (4)** — `test_app_smoke.py`: Health endpoint, CORS preflight, /generate and /publish endpoints exist
- **PDF Parser (9)** — `test_pdf_parser.py`: Returns dict with required keys, title extraction from programmatic PDF, abstract extraction, section structure, full text content, graceful handling of corrupt/empty bytes
- **Notebook Generator (14)** — `test_notebook_generator.py`: `build_notebook()` with markdown/code cells, nbformat validation, Colab metadata, kernelspec, `generate_notebook()` with mocked OpenAI client returns valid notebook + bullets
- **Gist Publisher (7)** — `test_gist_publisher.py`: Returns None without GITHUB_TOKEN, correct API URL/headers/payload with mocked httpx, Colab URL format, filename sanitization for special characters
- **Integration (12)** — `test_integration.py`: /health 200, /generate 422 on missing fields, /generate 400 on non-PDF, /stream 404 on invalid job_id, /publish 422/503 on missing fields/no token

### Frontend E2E: 12 Playwright tests
- **Scaffold (3)** — `task1_smoke.spec.js`: Page loads with heading, dark background color, app root visible
- **UI Shell (1)** — `task6_ui_shell.spec.js`: Theme colors (dark bg, green accent), Inter font
- **API Key Input (2)** — `task7_api_key.spec.js`: Container visible, password masking, show/hide toggle
- **PDF Upload (3)** — `task8_pdf_upload.spec.js`: Drop zone visible, button disabled without key, button enabled with file + key
- **Progress Display (3)** — `task9_progress.spec.js`: Not shown in idle state, other state-dependent components hidden
- **Result Card (3)** — `task10_result_card.spec.js`: Idle state structure, error state with reset, full layout

### Screenshots captured: 15 images in `tests/screenshots/`

## Security Measures

- **API key never stored**: The OpenAI key lives only in React `useState` — cleared on page refresh, never written to localStorage/cookies/disk, never logged server-side
- **API key never returned**: The `/generate` endpoint accepts the key but no endpoint ever returns it
- **CORS restricted**: Only `localhost:5173` and `127.0.0.1:5173` are allowed origins (not `*`)
- **File type validation**: PDF-only on both client (MIME type check) and server (`.pdf` extension check)
- **Dependency patching**: Upgraded FastAPI 0.115.6 → 0.135.2 and python-multipart 0.0.20 → 0.0.22 to fix 3 CVEs (CVE-2026-24486, CVE-2025-54121, CVE-2025-62727)
- **Static analysis**: semgrep with `p/python` ruleset — 0 findings across 151 rules on all backend files
- **npm audit**: 0 vulnerabilities in all frontend dependencies
- **Gist token isolation**: `GITHUB_TOKEN` is server-side only (`.env` file, excluded from git); missing token degrades gracefully to download-only mode

## Known Limitations

- **In-memory job store**: Jobs are lost on server restart. No persistence, no job cleanup. Will need Redis or similar for production.
- **No file size limit enforcement**: The PRD says 50MB max, but there's no server-side size check beyond what Uvicorn defaults to.
- **No rate limiting**: A user could flood the server with generation requests. Each request holds an OpenAI API call in the background.
- **Paper text truncation**: Only the first 12,000 characters of the paper are sent to GPT-4o. Very long papers will have their later sections cut off.
- **Single model**: Hardcoded to `gpt-4o`. The PRD originally specified `gpt-5.4` — should be configurable or upgraded when available.
- **No input sanitization on paper title**: The title extracted from the PDF is used in progress messages and the Gist filename. While the Gist publisher sanitizes the filename, the progress message doesn't escape HTML (not a risk in the current SSE→React pipeline, but worth noting).
- **No retry logic**: If the OpenAI API call fails (rate limit, timeout), the job immediately errors. No exponential backoff or retry.
- **EventSource limitations**: `EventSource` doesn't support custom headers, so the API key can't be sent via SSE — it's sent upfront with the POST. This is fine for v1 but means the SSE endpoint is unauthenticated.
- **No Gist cleanup**: Published Gists are never deleted. Over time this could accumulate many public Gists on the server's GitHub account.
- **PDF parsing is best-effort**: The title/abstract/section detection works well for standard academic papers (arXiv style) but may struggle with unusual layouts, scanned PDFs, or papers in non-English languages.

## What's Next

Based on the PRD trajectory and limitations above, v2 priorities should be:

1. **Authentication & usage tracking** — User accounts (email + OAuth), per-user generation history, usage quotas
2. **Production deployment** — Dockerize backend + frontend, deploy to a cloud provider, add Redis for job store persistence
3. **File size and rate limiting** — Enforce 50MB upload limit, add per-IP rate limiting, queue system for concurrent requests
4. **Model selection** — Let users choose between GPT-4o and newer models (gpt-5.4 when available), configurable max tokens
5. **Retry and resilience** — Exponential backoff on OpenAI failures, job timeout (5 min max), stale job cleanup
6. **Enhanced PDF parsing** — OCR support for scanned papers (Tesseract), better multi-column layout handling, table extraction
7. **Notebook quality feedback** — Let users rate generated notebooks, use feedback to improve the system prompt over time
