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

- [ ] Task 2: Build PDF parser module (P0)
  - Acceptance: `parse_pdf(bytes) -> dict` returns `{title, abstract, sections: [{heading, text}], full_text}` for any standard research paper PDF; tested with a sample paper
  - Files:
    - `backend/pdf_parser.py`

---

- [ ] Task 3: Build notebook generator — GPT-5.4 prompt + nbformat assembly (P0)
  - Acceptance: `generate_notebook(paper_dict, api_key) -> NotebookNode` calls GPT-5.4 with a structured system prompt and returns a valid `nbformat.v4` notebook with all 10 required sections (Title→Summary); notebook passes `nbformat.validate()`
  - Files:
    - `backend/notebook_generator.py` (contains `SYSTEM_PROMPT`, `analyze_paper()`, `build_notebook()`)
  - Notes: The GPT-5.4 prompt must instruct the model to: (a) infer algorithm type, (b) generate realistic synthetic data of appropriate scale, (c) write production-quality Python with type hints and docstrings, (d) include matplotlib visualizations, (e) write markdown cells with LaTeX equations where appropriate

---

- [ ] Task 4: Build GitHub Gist publisher for Colab link (P0)
  - Acceptance: `publish_to_gist(notebook_json, title) -> str` creates a public Gist and returns a valid `https://colab.research.google.com/gist/...` URL; uses `GITHUB_TOKEN` from env; gracefully returns `None` if token is missing (download-only fallback)
  - Files:
    - `backend/gist_publisher.py`

---

- [ ] Task 5: Build FastAPI endpoints with SSE progress streaming (P0)
  - Acceptance:
    - `POST /generate` accepts `multipart/form-data` with `api_key: str` + `file: UploadFile`; returns `{job_id: str}` immediately; launches background async task
    - `GET /stream/{job_id}` returns `text/event-stream`; emits `{type: "progress", message: str, elapsed: float}` events during processing; emits `{type: "done", notebook_b64: str, colab_url: str|null}` on completion; emits `{type: "error", message: str}` on failure
    - API key is forwarded to OpenAI per-request and never logged or stored
  - Files:
    - `backend/main.py` (complete implementation)
    - `backend/job_store.py` (in-memory dict for job state, fine for v1)

---

- [ ] Task 6: Build frontend UI shell — arcprize.org theme (P0)
  - Acceptance: App renders at localhost:5173 with: dark `#0d0d0d` background, centered 720px max-width layout, Inter font for headings, JetBrains Mono for code elements, page title "Paper → Notebook" with a subtle tagline; fully responsive
  - Files:
    - `frontend/src/App.jsx`
    - `frontend/src/index.css` (Tailwind base + custom CSS variables)
    - `frontend/public/` (any static assets)

---

- [ ] Task 7: Build API key input component (P0)
  - Acceptance: Component renders a password-type input with label "OpenAI API Key"; key stored in React state only; shows a lock icon + tooltip "Your key is never stored — used only for this session"; key persists across steps in current session; clears on page refresh
  - Files:
    - `frontend/src/components/APIKeyInput.jsx`

---

- [ ] Task 8: Build PDF upload + submit component (P0)
  - Acceptance: Drag-and-drop zone + file picker accepting `.pdf` only; shows file name and size on selection; "Generate Notebook" button disabled until both API key and PDF are provided; on submit, calls `POST /generate` and transitions to progress view
  - Files:
    - `frontend/src/components/PDFUpload.jsx`

---

- [ ] Task 9: Build SSE progress display component (P0)
  - Acceptance: Opens `GET /stream/{job_id}` via `EventSource`; renders a terminal-style scrolling log with timestamped messages (e.g. `[00:12] Analyzing core algorithms...`); green pulsing dot indicates "processing"; smoothly transitions to Result Card when `done` event is received; shows error state clearly if generation fails
  - Files:
    - `frontend/src/components/ProgressDisplay.jsx`

---

- [ ] Task 10: Build result card — download + Open in Colab (P0)
  - Acceptance: On `done` event received: (a) "Download .ipynb" button triggers browser download of the decoded notebook file named `{paper_title}_notebook.ipynb`; (b) "Open in Colab ↗" button appears only if `colab_url` is non-null and opens URL in new tab; result card shows paper title, a brief "What's in this notebook" summary (3 bullet points extracted from GPT response), and a "Generate Another" button that resets state; UI styled consistently with arcprize.org theme
  - Files:
    - `frontend/src/components/ResultCard.jsx`
    - Updates to `frontend/src/App.jsx` (wire all components into a state machine: `idle → processing → done | error`)
