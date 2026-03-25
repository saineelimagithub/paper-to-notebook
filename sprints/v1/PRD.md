# Sprint v1 — PRD: Research Paper → Colab Notebook Generator

## Overview
A single-page web application where researchers upload a research paper PDF, provide their OpenAI API key, and receive a production-quality Google Colab notebook that implements the paper's core algorithms and methodology as a runnable tutorial — complete with realistic synthetic data and structured explanations.

Target users are senior researchers and engineers at labs like OpenAI, DeepMind, and Google Brain who need to rapidly replicate and experiment with ideas from papers.

## Goals
- User can enter their OpenAI API key in the browser (session-only, never stored server-side)
- User can upload a research paper PDF (up to 50MB)
- Backend extracts and analyzes the paper using GPT-5.4 (reasoning model)
- A research-grade `.ipynb` notebook is generated with real algorithmic depth
- User can download the `.ipynb` file OR open it directly in Google Colab
- Processing screen shows live status messages so the user stays engaged during the 30–90 second wait

## User Stories
- As a researcher, I want to upload a PDF and get a runnable notebook, so I can start experimenting with a paper's ideas in minutes instead of hours
- As a researcher, I want the notebook to use realistic synthetic data (not toy examples), so I can trust it reflects real-world behavior of the algorithm
- As a researcher, I want live progress updates while the notebook generates, so I'm not staring at a blank screen
- As a researcher, I want to click "Open in Colab" and have it launch directly, so I don't have to manually upload the file
- As a researcher, I want my API key to stay private (not stored anywhere), so I can use my own account safely

## Technical Architecture

### Tech Stack
- **Frontend**: React 18 + Vite + Tailwind CSS (no component library — custom-styled to match arcprize.org aesthetic)
- **Backend**: Python FastAPI with Server-Sent Events (SSE) for streaming progress
- **PDF Parsing**: PyMuPDF (`fitz`) for text + layout extraction
- **AI Model**: OpenAI API — `gpt-5.4` (user-provided key, forwarded per-request)
- **Notebook Assembly**: `nbformat` Python library to build `.ipynb` files programmatically
- **Colab Integration**: GitHub Gist API (server-side token in `.env`) to publish notebook and return a `colab.research.google.com/gist/...` URL

### Component Diagram
```
┌──────────────────────────────────────────────────────────────────┐
│                        Browser (React)                           │
│                                                                  │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────────┐  │
│  │ API Key     │   │ PDF Upload   │   │ Progress Display     │  │
│  │ Input       │   │ Drop Zone    │   │ (SSE stream)         │  │
│  └─────────────┘   └──────────────┘   └──────────────────────┘  │
│                                                                  │
│                    ┌──────────────────────────┐                  │
│                    │ Result Card              │                  │
│                    │ [Download .ipynb]        │                  │
│                    │ [Open in Colab ↗]        │                  │
│                    └──────────────────────────┘                  │
└──────────────────────────────────────────────────────────────────┘
                              │  HTTP + SSE
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                              │
│                                                                  │
│  POST /generate  ──▶  pdf_parser.py                             │
│  (multipart form:       └─▶ extract_text_and_structure()        │
│   api_key + pdf)                                                 │
│                         notebook_generator.py                   │
│                           └─▶ analyze_paper()  [GPT-5.4]        │
│                           └─▶ build_notebook() [nbformat]       │
│                                                                  │
│  GET /stream/{id}  ──▶  SSE progress events                     │
│                                                                  │
│  POST /publish     ──▶  gist_publisher.py                       │
│                           └─▶ GitHub Gist API                   │
│                           └─▶ returns colab.research.google.com │
│                                /gist/{gist_id}                  │
└──────────────────────────────────────────────────────────────────┘
```

### Data Flow
1. User enters OpenAI API key → stored in React state only (never serialized)
2. User uploads PDF → `POST /generate` (multipart: `api_key` + `file`)
3. Backend assigns a job `id`, starts async processing, returns `{job_id}`
4. Frontend opens `GET /stream/{job_id}` (SSE) — receives progress events
5. Backend: extract PDF text → send event → call GPT-5.4 → send events → build `.ipynb` → send done event with base64 notebook payload
6. Frontend decodes notebook, enables download button + triggers Gist publish
7. `POST /publish` → backend creates GitHub Gist → returns Colab URL

### Notebook Structure (Generated by GPT-5.4)
Each notebook must contain these sections as markdown + code cell pairs:
```
[1] Title, Authors, Abstract Summary          (markdown)
[2] Installation & Imports                    (code)
[3] Paper Overview & Theoretical Background  (markdown + equations)
[4] Core Algorithm — Pseudocode Walkthrough  (markdown)
[5] Algorithm Implementation                  (code — fully runnable)
[6] Synthetic Dataset Generation              (code — realistic, not toy)
[7] Experiment: Reproduce Key Results         (code)
[8] Visualization & Analysis                  (code — matplotlib/seaborn)
[9] Ablation Study / Sensitivity Analysis     (code)
[10] Summary & Next Steps                     (markdown)
```

### UI Theme — arcprize.org Inspired
- Background: `#0d0d0d` (near-black)
- Accent: `#e8e8e8` (off-white text) + `#4ade80` (green highlights for status)
- Font: `Inter` (headings) + `JetBrains Mono` (code/monospace elements)
- Layout: centered single-column, max-width 720px, generous whitespace
- Progress display: terminal-style log with timestamped messages

### Progress Messages (shown during generation)
```
[00:01] Parsing PDF structure and extracting text...
[00:03] Identifying paper type: {detected_type}
[00:06] Analyzing core algorithms and theoretical contributions...
[00:12] Mapping methodology to implementable components...
[00:20] Designing realistic synthetic dataset schema...
[00:28] Generating algorithm implementation (Section 3)...
[00:45] Writing experimental validation cells...
[00:58] Assembling notebook structure...
[01:10] Notebook ready. Preparing download...
```

## Out of Scope (v2+)
- User authentication / accounts
- Usage tracking and rate limiting
- Saving notebooks to a personal library
- Multiple paper uploads in one session
- Team/organization features
- Streaming notebook cell-by-cell as it generates
- Support for papers with heavy math (LaTeX rendering in notebook)
- Fine-tuning on specific paper domains

## Dependencies
- OpenAI API access (user-provided key, GPT-5.4 model)
- GitHub Personal Access Token with `gist` scope (server `.env` — for Colab link feature)
- Python 3.11+, Node.js 18+
