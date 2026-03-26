# Sprint v2 — PRD: Security Hardening

## Overview
Harden the Paper → Notebook application against the OWASP Top 10 vulnerabilities identified in the v1 security review. This sprint addresses prompt injection via PDF content, denial-of-service vectors (unbounded uploads, memory exhaustion), API key exposure, missing security headers, and information leakage — all without adding new user-facing features.

After this sprint, the application should be resilient against malicious PDF uploads, resource exhaustion attacks, and common web security misconfigurations while remaining a locally-run tool.

## Goals
- Uploaded PDFs cannot inject malicious instructions into Gemini that produce dangerous executable code
- Server cannot be crashed via oversized uploads or unbounded job accumulation
- API keys are transmitted securely via headers (not form bodies) and never appear in logs or error messages
- All API responses include security headers (CSP, X-Content-Type-Options, X-Frame-Options)
- Error messages shown to users are generic; full details are logged server-side only
- Rate limiting prevents abuse of `/generate` and `/publish` endpoints
- GitHub Gists default to secret (not public)
- Stale jobs are automatically cleaned up via TTL

## User Stories
- As a researcher, I want uploaded PDFs to be scanned before processing, so that a malicious PDF cannot trick the AI into generating harmful code
- As a researcher, I want generated notebook code cells to be scanned for suspicious patterns, so that I can trust the output before running it in Colab
- As a researcher, I want my API key sent securely via headers, so that it is not logged by proxies or intermediaries
- As a researcher, I want clear but generic error messages, so that internal server details are never exposed to me
- As an operator, I want the server to reject oversized uploads and limit request rates, so that the service stays available under load
- As an operator, I want stale jobs to be cleaned up automatically, so that memory usage stays bounded

## Technical Architecture

### Tech Stack (unchanged from v1)
- **Frontend**: React 18 + Vite + Tailwind CSS
- **Backend**: Python FastAPI with SSE
- **PDF Parsing**: PyMuPDF (fitz)
- **AI Model**: Gemini 2.5 Flash (user-provided key)
- **Notebook Assembly**: nbformat
- **Colab Integration**: GitHub Gist API

### New Security Components
```
┌──────────────────────────────────────────────────────────────────┐
│                        Browser (React)                           │
│                                                                  │
│  APIKeyInput ──▶ X-Api-Key header (not form body)               │
│  PDFUpload   ──▶ Client-side 20MB size check                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                               │
│                                                                  │
│  ┌────────────────┐                                              │
│  │ Security       │  Middleware layer (applied to ALL responses) │
│  │ Middleware      │  ├─ Security headers (CSP, X-Frame, etc.)  │
│  │                │  ├─ Rate limiter (slowapi: /generate,       │
│  │                │  │   /publish)                               │
│  │                │  └─ Request size limit (20MB)                │
│  └────────────────┘                                              │
│                                                                  │
│  POST /generate ──▶ pdf_parser.py                                │
│   (X-Api-Key hdr)    └─▶ [NEW] input_sanitizer.py               │
│   (file: PDF)              └─▶ Strip control chars, escape       │
│                                 prompt injection patterns        │
│                                                                  │
│                    notebook_generator.py                          │
│                      └─▶ Gemini API call                         │
│                      └─▶ [NEW] notebook_scanner.py               │
│                            └─▶ Post-generation code cell scan    │
│                            └─▶ Flag: os.system, subprocess,      │
│                                 eval, exec, network calls,       │
│                                 file I/O to sensitive paths      │
│                                                                  │
│  job_store.py                                                    │
│   └─▶ [NEW] TTL cleanup (30 min) via background task            │
│                                                                  │
│  gist_publisher.py                                               │
│   └─▶ "public": False (secret gists)                            │
│                                                                  │
│  [NEW] error_handler.py                                          │
│   └─▶ Generic user-facing messages + server-side logging         │
└──────────────────────────────────────────────────────────────────┘
```

### Security Data Flow (changes from v1)
1. User enters API key → stored in React state (unchanged)
2. User uploads PDF → **client-side 20MB check** → reject if over limit
3. `POST /generate` — API key now in `X-Api-Key` header, PDF in multipart body
4. **Server-side size check** — reject if `> 20MB` with HTTP 413
5. **Rate limiter** — reject if `> 5 req/min` per IP with HTTP 429
6. PDF parsing → **input sanitizer** strips control characters and known prompt injection patterns from extracted text before sending to Gemini
7. Gemini generates notebook → **notebook scanner** inspects every code cell for:
   - `os.system()`, `subprocess.*`, `eval()`, `exec()`
   - `open()` targeting sensitive paths (`/etc/`, `.env`, `~/.ssh/`)
   - Network calls to non-standard domains (`requests.get`, `urllib`, `socket`)
   - Base64-encoded payloads that decode to suspicious content
   - `__import__()` dynamic imports
8. If scanner finds issues → flag in response so frontend can warn user
9. Error handling → generic message to client, full traceback to server log
10. Job TTL → background task runs every 60s, evicts jobs older than 30 min

## Out of Scope (v3+)
- User authentication / accounts
- Production deployment (Docker, cloud, HTTPS)
- Redis-backed job store
- Sandboxed code execution for generated notebooks
- WAF / DDoS protection
- Penetration testing
- HTTPS / TLS configuration (local-only in v2)

## Dependencies
- Sprint v1 complete (all 10 tasks done)
- `slowapi` Python package for rate limiting
- Python `logging` module (stdlib) for structured server-side logs
