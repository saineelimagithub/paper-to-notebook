# Sprint v1 — Tasks

## Status: In Progress

---

- [x] Task 1: Scaffold project structure and install dependencies (P0)
  - Acceptance: Running `uvicorn main:app` starts backend on :8000; running `npm run dev` starts frontend on :5173; no errors
  - Files:
    - `backend/main.py` (FastAPI skeleton with CORS)
    - `backend/requirements.txt` (fastapi, uvicorn, pymupdf, openai, nbformat, httpx, python-multipart)
    - `frontend/package.json` (react, vite, tailwindcss)
    - `frontend/vite.config.js`
    - `frontend/tailwind.config.js`
    - `frontend/index.html`
    - `frontend/src/main.jsx`
    - `frontend/src/App.jsx` (empty shell)
    - `backend/.env.example` (GITHUB_TOKEN=your_token_here)
  - Completed: 2026-03-25 — Full scaffold with arcprize.org dark theme; 4 backend tests + 3 Playwright E2E tests all green; security: semgrep 0 findings, upgraded fastapi→0.135.2 + python-multipart→0.0.22 to fix CVE-2026-24486, CVE-2025-54121, CVE-2025-62727

---

- [x] Task 2: Build PDF parser module (P0)
  - Acceptance: `parse_pdf(bytes) -> dict` returns `{title, abstract, sections: [{heading, text}], full_text}` for any standard research paper PDF; tested with a sample paper
  - Files:
    - `backend/pdf_parser.py`
  - Completed: 2026-03-25 — Full PyMuPDF implementation with title detection (largest font on page 1), abstract extraction (regex heading match), section detection (ALL CAPS / Title Case / common paper headings), graceful error handling for corrupt/empty bytes; 9 tests passing; security: semgrep 0 findings

---

- [x] Task 3: Build notebook generator — GPT-4o prompt + nbformat assembly (P0)
  - Acceptance: `generate_notebook(paper_dict, api_key) -> NotebookNode` calls gpt-4o with a structured system prompt and returns a valid `nbformat.v4` notebook with all 10 required sections (Title→Summary); notebook passes `nbformat.validate()`
  - Files:
    - `backend/notebook_generator.py` (contains `SYSTEM_PROMPT`, `generate_notebook()`, `build_notebook()`)
  - Notes: Uses gpt-4o (not gpt-5.4 which may not be available). System prompt instructs model to: (a) infer algorithm type, (b) generate realistic synthetic data of appropriate scale, (c) write production-quality Python with type hints and docstrings, (d) include matplotlib visualizations, (e) write markdown cells with LaTeX equations
  - Completed: 2026-03-25 — Full async implementation with OpenAI gpt-4o, JSON response format, nbformat v4 assembly with Colab metadata; 14 tests passing (mocked OpenAI); security: semgrep 0 findings

---

- [x] Task 4: Build GitHub Gist publisher for Colab link (P0)
  - Acceptance: `publish_to_gist(notebook_json, title) -> str` creates a public Gist and returns a valid `https://colab.research.google.com/gist/...` URL; uses `GITHUB_TOKEN` from env; gracefully returns `None` if token is missing (download-only fallback)
  - Files:
    - `backend/gist_publisher.py`
  - Completed: 2026-03-25 — httpx-based implementation with filename sanitization (alphanumeric + space/hyphen/underscore, truncated to 80 chars), correct GitHub API v2022-11-28 headers, Bearer token auth, graceful None return when no token; 7 tests passing (mocked httpx); security: semgrep 0 findings

---

- [x] Task 5: Build FastAPI endpoints with SSE progress streaming (P0)
  - Acceptance:
    - `POST /generate` accepts `multipart/form-data` with `api_key: str` + `file: UploadFile`; returns `{job_id: str}` immediately; launches background async task
    - `GET /stream/{job_id}` returns `text/event-stream`; emits `{type: "progress", message: str, elapsed: float}` events during processing; emits `{type: "done", notebook_b64: str, colab_url: str|null}` on completion; emits `{type: "error", message: str}` on failure
    - API key is forwarded to OpenAI per-request and never logged or stored
  - Files:
    - `backend/main.py` (complete implementation — done in Task 1)
    - `backend/job_store.py` (in-memory dict for job state)
  - Completed: 2026-03-25 — Full integration tests added verifying /health 200, /generate 422 on missing fields, /generate 400 on non-PDF, /stream 404 on invalid job_id, /publish 422/503 on missing fields/token; 12 tests passing; security: semgrep 0 findings (all backend: 46 tests passing)

---

- [x] Task 6: Build frontend UI shell — arcprize.org theme (P0)
  - Acceptance: App renders at localhost:5173 with: dark `#0d0d0d` background, centered 720px max-width layout, Inter font for headings, JetBrains Mono for code elements, page title "Paper → Notebook" with a subtle tagline; fully responsive
  - Files:
    - `frontend/src/App.jsx`
    - `frontend/src/index.css` (Tailwind base + custom CSS variables)
  - Completed: 2026-03-25 — Playwright test verifies dark bg (#0d0d0d = rgb(13,13,13)), green accent on "Research Tool" label (#4ade80 = rgb(74,222,128)), Inter font on h1; screenshot saved to tests/screenshots/task6-01-ui-shell.png; npm audit: 0 vulnerabilities

---

- [x] Task 7: Build API key input component (P0)
  - Acceptance: Component renders a password-type input with label "OpenAI API Key"; key stored in React state only; shows a lock icon + tooltip "Your key is never stored — used only for this session"; key persists across steps in current session; clears on page refresh
  - Files:
    - `frontend/src/components/APIKeyInput.jsx`
  - Completed: 2026-03-25 — Password input with show/hide toggle, security note, data-testid attributes; Playwright tests verify: container visible, password type by default, key typed, toggle to text, toggle back to password; 2 tests passing; screenshots: task7-01,02,03

---

- [x] Task 8: Build PDF upload + submit component (P0)
  - Acceptance: Drag-and-drop zone + file picker accepting `.pdf` only; shows file name and size on selection; "Generate Notebook" button disabled until both API key and PDF are provided; on submit, calls `POST /generate` and transitions to progress view
  - Files:
    - `frontend/src/components/PDFUpload.jsx`
  - Completed: 2026-03-25 — Drag-and-drop + click-to-browse zone, PDF-only filter, file name/size display, disabled button state logic, FormData submission; 3 Playwright tests passing (drop zone visible, button disabled without key, button enabled with file+key); screenshots: task8-01,02,03

---

- [x] Task 9: Build SSE progress display component (P0)
  - Acceptance: Opens `GET /stream/{job_id}` via `EventSource`; renders a terminal-style scrolling log with timestamped messages (e.g. `[00:12] Analyzing core algorithms...`); green pulsing dot indicates "processing"; smoothly transitions to Result Card when `done` event is received; shows error state clearly if generation fails
  - Files:
    - `frontend/src/components/ProgressDisplay.jsx`
  - Completed: 2026-03-25 — EventSource-based SSE consumer, timestamped log messages, pulsing green dot for connecting/running, static dot for done, red dot for error, auto-scroll; 3 Playwright tests verify progress display hidden in idle state, result card hidden, error state hidden; screenshot: task9-01

---

- [x] Task 10: Build result card — download + Open in Colab (P0)
  - Acceptance: On `done` event received: (a) "Download .ipynb" button triggers browser download of the decoded notebook file named `{paper_title}_notebook.ipynb`; (b) "Open in Colab ↗" button appears only if `colab_url` is non-null and opens URL in new tab; result card shows paper title, a brief "What's in this notebook" summary (3 bullet points extracted from GPT response), and a "Generate Another" button that resets state; UI styled consistently with arcprize.org theme
  - Files:
    - `frontend/src/components/ResultCard.jsx`
    - Updates to `frontend/src/App.jsx` (wire all components into a state machine: `idle → processing → done | error`)
  - Completed: 2026-03-25 — Full state machine (idle→processing→done|error), ResultCard with atob download + Colab link, reset to idle; 3 Playwright tests passing (idle state structure, error state with reset, full layout screenshot); screenshots: task10-01,02,03,04; npm audit: 0 vulnerabilities
