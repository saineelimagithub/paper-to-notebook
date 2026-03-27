# Sprint v2 — Walkthrough

## Summary
Sprint v2 is a pure security hardening sprint that implements defense-in-depth protections across the Paper → Notebook Generator without adding new user-facing features. It addresses all 11 vulnerabilities identified in the v1 security audit: prompt injection via PDF content, denial-of-service vectors (unbounded uploads, memory exhaustion), API key exposure in form bodies, missing security headers, information leakage through raw exceptions, and public Gist URLs. After this sprint, the application has 107 passing tests, 0 semgrep findings, and 0 npm audit vulnerabilities.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        Browser (React)                           │
│                                                                  │
│  APIKeyInput ──▶ X-Api-Key header (not form body)  [Task 3]     │
│  PDFUpload   ──▶ Client-side 20MB check            [Task 2]     │
│  ResultCard  ──▶ Security warnings + acknowledge    [Task 7]     │
│                                                                  │
└──────────────────────────┬───────────────────────────────────────┘
                           │ POST /generate (X-Api-Key header)
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                               │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ Middleware Stack (applied to ALL responses)              │     │
│  │ ├─ SecurityHeadersMiddleware (5 headers)      [Task 1]  │     │
│  │ ├─ CORSMiddleware (tightened allow_headers)   [Task 1]  │     │
│  │ └─ Rate Limiter (slowapi, per-IP)             [Task 4]  │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  POST /generate                                                  │
│   ├─ 20MB upload limit check                     [Task 2]       │
│   ├─ Max concurrent jobs (20) → 503              [Task 9]       │
│   └─ Background task: _run_generation()                          │
│       ├─ pdf_parser.py → extract text                            │
│       ├─ input_sanitizer.py (NEW)                [Task 5]       │
│       │   ├─ Strip Unicode control chars                         │
│       │   ├─ Neutralize prompt injection patterns                │
│       │   └─ Truncate to 12k chars                               │
│       ├─ notebook_generator.py → Gemini 2.5 Flash                │
│       ├─ notebook_scanner.py (NEW)               [Task 6]       │
│       │   └─ 12 rules: os.system, subprocess, eval, exec, ...   │
│       └─ error_handler.py (NEW)                  [Task 8]       │
│           └─ Generic user messages, full server-side logging     │
│                                                                  │
│  GET /stream/{job_id}                                            │
│   └─ UUID format validation → 400 if invalid     [Task 10]      │
│                                                                  │
│  job_store.py                                                    │
│   ├─ TTL cleanup every 60s (evicts > 30 min)     [Task 9]       │
│   └─ MAX_JOBS = 20 capacity cap                  [Task 9]       │
│                                                                  │
│  gist_publisher.py                                               │
│   └─ "public": false (secret gists)              [Task 10]      │
└──────────────────────────────────────────────────────────────────┘
```

## Files Created/Modified

### backend/main.py (Modified)
**Purpose**: Core FastAPI application — routes, middleware, and background generation task.

**Key Changes**:
- `SecurityHeadersMiddleware` — adds 5 security headers to every response
- `rate_limit_handler()` — custom 429 handler for slowapi
- `generate()` — now reads API key from `X-Api-Key` header, checks 20MB limit, enforces job cap
- `_run_generation()` — unpacks 3-tuple from `generate_notebook()`, includes `findings` in SSE done event
- `stream_job()` — validates UUID format before job lookup
- `_periodic_cleanup()` — asyncio background task that calls `cleanup_stale_jobs()` every 60s
- `lifespan()` — manages the cleanup task lifecycle

**How it works**:
The middleware stack processes every request in order: SecurityHeadersMiddleware appends five hardened response headers (CSP, X-Frame-Options, etc.), CORSMiddleware restricts allowed headers to `["Content-Type", "X-Api-Key"]` (was `["*"]`), and slowapi enforces per-IP rate limits (5/min for `/generate`, 10/min for `/publish`).

The `/generate` endpoint reads the API key from the `X-Api-Key` request header instead of a form field, preventing proxy/intermediary logging. It checks file size server-side (20MB cap) and rejects with HTTP 413 if exceeded. Before creating a job, it checks `create_job()` — which returns `None` if the store is at the 20-job cap, triggering HTTP 503.

The background task `_run_generation()` now receives security findings from the notebook scanner via a 3-tuple return from `generate_notebook()`. These findings are included in the SSE `done` event payload so the frontend can display warnings.

```python
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response
```

---

### backend/input_sanitizer.py (New)
**Purpose**: Pre-Gemini defense layer — sanitizes PDF-extracted text to prevent prompt injection.

**Key Functions**:
- `sanitize_paper_text(paper: dict) -> dict` — main entry point, returns a sanitized copy
- `_neutralize_injections(text: str) -> str` — prefixes injection lines with `[USER TEXT]:`

**How it works**:
This module implements the first layer of the two-layer prompt injection defense. Before any extracted text is sent to Gemini, it passes through three sanitization stages:

1. **Unicode control character stripping**: Removes zero-width characters (U+200B–200F), bidirectional overrides (U+202A–202E), invisible operators (U+2060–2064), and BOM (U+FEFF) from title, abstract, full_text, and section headings/text. These characters can be embedded in PDFs to trick text processing.

2. **Prompt injection neutralization**: Scans each line of `full_text` against 7+ regex patterns that detect common role-override phrases ("ignore previous instructions", "you are now", "new instructions:", "system:", "ADMIN:", etc.). Matching lines are prefixed with `[USER TEXT]:` to disambiguate them from actual system instructions, rather than removing them (which could lose legitimate academic text).

3. **Truncation**: Caps `full_text` at 12,000 characters, enforced at the sanitizer level rather than relying on downstream modules.

```python
_INJECTION_PATTERNS = re.compile(
    r"^.*("
    r"ignore\s+(?:all\s+)?(?:previous\s+)?instructions"
    r"|you\s+are\s+now"
    r"|new\s+instructions\s*:"
    r"|^system\s*:"
    r"|^admin\s*:"
    r"|disregard\s+(?:all\s+)?(?:previous\s+)?(?:instructions|prompts)"
    r"|override\s+(?:all\s+)?(?:safety|security)"
    r"|forget\s+(?:all\s+)?(?:previous\s+)?(?:instructions|rules)"
    r").*$",
    re.IGNORECASE | re.MULTILINE,
)
```

---

### backend/notebook_scanner.py (New)
**Purpose**: Post-generation defense layer — scans generated code cells for dangerous patterns before delivering to the user.

**Key Functions**:
- `scan_notebook(cells: list[dict]) -> list[dict]` — returns list of findings (empty if clean)

**How it works**:
This is the second layer of the prompt injection defense. After Gemini generates notebook cells, every code cell is scanned line-by-line against 12 regex-based detection rules:

| Pattern | Severity | What it detects |
|---------|----------|-----------------|
| `os.system()` | critical | Shell command execution |
| `subprocess.*()` | critical | Subprocess module calls |
| `Popen()` | critical | Direct process creation |
| `eval()` | critical | Dynamic code evaluation |
| `exec()` | critical | Dynamic code execution |
| `__import__()` | warning | Dynamic module imports |
| `open()` + sensitive path | critical | File access to /etc/, .env, .ssh, ~/ |
| `requests.get/post` | warning | HTTP requests to external URLs |
| `urllib.request.urlopen` | warning | HTTP via urllib |
| `.connect((` | critical | Raw socket connections |
| `shutil.rmtree()` | critical | Recursive directory deletion |
| `os.remove()` | warning | File deletion |

Each finding includes cell_index, line number, pattern name, severity level, and a human-readable description. Markdown cells are skipped (only code cells are scanned). The findings are returned to `_run_generation()` and forwarded to the frontend via the SSE done event.

```python
def scan_notebook(cells: list[dict]) -> list[dict]:
    findings: list[dict] = []
    for cell_idx, cell in enumerate(cells):
        if cell.get("type") != "code":
            continue
        source = cell.get("source", "")
        lines = source.split("\n")
        for line_idx, line in enumerate(lines, start=1):
            for regex, pattern_name, severity, description in _RULES:
                if regex.search(line):
                    findings.append({
                        "cell_index": cell_idx,
                        "line": line_idx,
                        "pattern": pattern_name,
                        "severity": severity,
                        "description": description,
                    })
    return findings
```

---

### backend/error_handler.py (New)
**Purpose**: Maps exceptions to safe, generic user-facing messages while logging full details server-side.

**Key Functions**:
- `safe_error_message(exc: Exception) -> str` — classifies and returns a generic message

**How it works**:
When `_run_generation()` catches an exception, instead of sending `str(exc)` (which could leak file paths, API keys, or stack traces), it calls `safe_error_message()`. The function:

1. Logs the full exception with traceback via Python `logging` at ERROR level (server-side only)
2. Classifies the error using regex against the exception string:
   - Auth patterns (401, 403, unauthorized, invalid key) → `"Invalid API key."`
   - PDF patterns (fitz, pymupdf, cannot open, parse error) → `"PDF could not be parsed."`
   - Everything else → `"Generation failed. Please try again."`

This ensures that internal details never reach the user's browser, while operators can still diagnose issues from server logs.

---

### backend/job_store.py (Modified)
**Purpose**: In-memory job store with TTL-based eviction and capacity limits.

**Key Changes**:
- `MAX_JOBS = 20` — concurrent job capacity cap
- `JOB_TTL_SECONDS = 1800` — 30-minute job lifetime
- `Job.created_at: float` — monotonic timestamp for TTL calculations
- `JobEvent.findings: list` — carries security scan findings in done events
- `create_job()` — returns `None` when at capacity (triggers 503 upstream)
- `cleanup_stale_jobs()` — evicts jobs older than TTL, returns count

**How it works**:
The job store uses `time.monotonic()` for TTL timestamps, which is immune to system clock adjustments. When `create_job()` is called and `len(_jobs) >= MAX_JOBS`, it returns `None` rather than creating a job — the calling code in `main.py` translates this to HTTP 503. The `cleanup_stale_jobs()` function is called every 60 seconds by the `_periodic_cleanup()` background task, removing any job whose `created_at` is more than 30 minutes old.

```python
def create_job(job_id: str) -> Job | None:
    if len(_jobs) >= MAX_JOBS:
        return None
    job = Job(job_id=job_id)
    _jobs[job_id] = job
    return job
```

---

### backend/notebook_generator.py (Modified)
**Purpose**: Gemini 2.5 Flash integration — generates research notebooks from parsed papers.

**Key Changes**:
- Calls `sanitize_paper_text(paper)` before building the Gemini prompt
- Calls `scan_notebook(result["cells"])` after building the notebook
- Returns a 3-tuple: `(notebook, summary_bullets, findings)` instead of a 2-tuple

**How it works**:
The generator now acts as the orchestration point for both security layers. Before sending text to Gemini, it imports and calls `sanitize_paper_text()` to clean the extracted paper content. After receiving and parsing Gemini's JSON response, it imports and calls `scan_notebook()` to inspect the generated code cells. The findings list (possibly empty) is returned as the third element of the tuple, flowing up through `_run_generation()` to the SSE stream and ultimately to the frontend.

---

### backend/gist_publisher.py (Modified)
**Purpose**: Publishes notebooks as GitHub Gists and returns Colab URLs.

**Key Change**: `"public": False` — gists are now created as secret (URL-accessible but not listed on the user's public profile).

---

### backend/requirements.txt (Modified)
**Purpose**: Python dependency manifest.

**Key Change**: Added `slowapi==0.1.9` for rate limiting.

---

### frontend/src/App.jsx (Modified)
**Purpose**: Top-level React shell managing the idle → processing → done | error state machine.

**Key Changes**:
- `handleSubmit()` sends API key via `headers: {"X-Api-Key": key}` instead of form body
- `handleDone()` extracts `findings` from SSE event data
- Passes `findings` prop to `ResultCard`

---

### frontend/src/components/PDFUpload.jsx (Modified)
**Purpose**: Drag-and-drop PDF upload component with file validation.

**Key Changes**:
- Client-side 20MB size check via `MAX_SIZE = 20 * 1024 * 1024`
- `fileOversize` derived state disables the submit button
- Shows red warning text `"— exceeds 20MB limit"` next to file size
- `onSubmit(formData, apiKey)` passes API key separately from form data

---

### frontend/src/components/ResultCard.jsx (Modified)
**Purpose**: Displays generation results with download/Colab buttons and security warnings.

**Key Changes**:
- Yellow warning banner (`data-testid="security-warnings"`) listing each finding with severity color coding
- Acknowledge-before-download flow: download/Colab buttons are hidden until user clicks "I understand the risks, show download options"
- Severity-based coloring: `critical` findings in red, `warning` in yellow

**How it works**:
When `findings` is non-empty, the component renders a yellow-bordered warning section showing each finding's severity, cell index, line number, and description. The download and Colab buttons are replaced with an acknowledgement prompt. Only after the user clicks the acknowledge button (`setAcknowledged(true)`) do the download options appear. This prevents users from accidentally running notebooks with flagged code patterns without awareness.

---

### .gitignore (Modified)
**Purpose**: Git ignore rules for the project.

**Key Change**: Changed `backend/.env` to global `*.env` pattern with `!*.env.example` exception, providing broader secret protection.

---

## Data Flow

```
1. User enters Gemini API key → stored in React state (never persisted)
2. User drops PDF onto upload zone
   → Client checks file.size > 20MB → red warning, submit disabled
3. User clicks "Generate Notebook"
   → POST /generate with X-Api-Key header + multipart PDF body
4. FastAPI middleware stack:
   → SecurityHeadersMiddleware adds 5 headers to response
   → slowapi checks 5/min rate limit per IP → 429 if exceeded
5. Route handler:
   → Validates .pdf extension → 400 if not PDF
   → Reads bytes, checks > 20MB → 413 if oversized
   → create_job() → 503 if at 20-job capacity
   → Returns {job_id} immediately, starts background task
6. Background task (_run_generation):
   → pdf_parser.parse_pdf() extracts title, abstract, full_text, sections
   → input_sanitizer.sanitize_paper_text() strips control chars,
     neutralizes injection patterns, truncates to 12k chars
   → notebook_generator sends sanitized text to Gemini 2.5 Flash
   → Gemini returns JSON with cells array + summary bullets
   → notebook_scanner.scan_notebook() inspects code cells (12 rules)
   → nbformat builds valid .ipynb NotebookNode
   → gist_publisher creates secret Gist → Colab URL
   → SSE done event with notebook_b64 + colab_url + findings
7. Frontend receives SSE events:
   → ProgressDisplay shows streaming progress messages
   → On "done": ResultCard renders with bullets, download, Colab link
   → If findings present: yellow warning banner, acknowledge-before-download
8. Error path:
   → error_handler.safe_error_message() classifies exception
   → Generic message sent via SSE error event
   → Full traceback logged server-side only
9. Background cleanup:
   → Every 60s, cleanup_stale_jobs() evicts jobs older than 30 min
```

## Test Coverage

**107 tests total, all passing.**

- **Security Headers** (5 tests) — `test_security_headers.py`
  - Verifies all 5 headers present on `/health` response
  - Checks exact header values (CSP, X-Frame-Options, etc.)
  - Validates CORS allow_headers is explicit list

- **Upload Limits** (3 tests) — `test_upload_limits.py`
  - File under 20MB accepted
  - File over 20MB returns 413
  - Exact error message verification

- **Rate Limiting** (3 tests) — `test_rate_limiting.py`
  - Requests within limit succeed
  - 6th request in a minute returns 429
  - Uses autouse fixture to reset limiter between tests

- **Input Sanitizer** (15 tests) — `test_input_sanitizer.py`
  - Control character stripping from all text fields
  - Each injection pattern detected and neutralized
  - `[USER TEXT]:` prefix applied to injection lines
  - Clean text passes through unchanged
  - Truncation at 12,000 characters
  - Section sanitization

- **Notebook Scanner** (18 tests) — `test_notebook_scanner.py`
  - Each of 12 detection rules tested individually
  - Markdown cells ignored
  - Clean notebooks return empty findings
  - Correct cell_index and line numbers
  - Severity levels verified (critical vs warning)

- **Error Handler** (10 tests) — `test_error_handler.py`
  - Auth errors classified correctly (401, 403, invalid key)
  - PDF errors classified correctly (fitz, pymupdf, parse error)
  - Generic fallback for unknown errors
  - No file paths leaked in messages
  - No stack traces leaked in messages
  - No API keys leaked in messages
  - Server-side logging verified

- **Job Cleanup** (7 tests) — `test_job_cleanup.py`
  - Old jobs evicted after TTL
  - Active jobs preserved
  - MAX_JOBS cap enforced (returns None at capacity)
  - cleanup_stale_jobs returns correct eviction count

- **Integration** (12 tests) — `test_integration.py`
  - Health endpoint, generate with/without API key header
  - Non-PDF rejection, valid PDF acceptance
  - Stream with unknown UUID (404), invalid UUID format (400)
  - Publish with missing fields, missing GITHUB_TOKEN

- **Gist Publisher** (tests updated) — `test_gist_publisher.py`
  - Verifies `"public": false` in API payload

- **Notebook Generator** (tests updated) — `test_notebook_generator.py`
  - Updated to unpack 3-tuple return value (notebook, bullets, findings)

## Security Measures

| # | Measure | Layer | OWASP Category |
|---|---------|-------|----------------|
| 1 | Security response headers (CSP, X-Frame, X-Content-Type, Referrer-Policy, Permissions-Policy) | HTTP | A05: Security Misconfiguration |
| 2 | CORS tightened from `["*"]` to explicit `["Content-Type", "X-Api-Key"]` | HTTP | A05: Security Misconfiguration |
| 3 | 20MB upload limit (client + server) | Transport | A06: Vulnerable Components |
| 4 | API key moved from form body to X-Api-Key header | Transport | A07: Identification Failures |
| 5 | Rate limiting: 5/min generate, 10/min publish (per IP) | Application | A04: Insecure Design |
| 6 | Input sanitization: control chars stripped, injection patterns neutralized | Application | A03: Injection |
| 7 | Post-generation code scanning (12 rules, 2 severity levels) | Application | A03: Injection |
| 8 | Safe error handler: generic messages to user, full logs server-side | Application | A09: Security Logging/Monitoring |
| 9 | TTL job cleanup (30 min) + 20-job capacity cap | Resource | A04: Insecure Design |
| 10 | Secret GitHub Gists (not publicly listed) | External | A01: Broken Access Control |
| 11 | UUID validation on /stream endpoint (400 for invalid format) | Application | A01: Broken Access Control |
| 12 | Global `*.env` gitignore pattern | SCM | A02: Cryptographic Failures |

## Known Limitations

- **In-memory job store**: All jobs are lost on server restart. Not suitable for multi-process or multi-server deployments. Redis would be needed for production.
- **Rate limiting is per-IP in-memory**: Behind a reverse proxy, all users may share the same IP. Rate limit state is lost on restart.
- **Input sanitizer is pattern-based**: Novel prompt injection techniques not matching the 7+ known patterns will pass through. Adversarial researchers will find bypasses.
- **Notebook scanner is regex-based**: Obfuscated code (base64-encoded payloads, `getattr` tricks, encoded eval) will evade detection. The scanner catches common patterns, not determined adversaries.
- **No authentication**: Any user on the network can access all endpoints. API key is for Gemini only, not app access control.
- **No HTTPS**: Running locally on HTTP. API keys transit in cleartext on the local network.
- **No request body logging or audit trail**: Failed attacks are not recorded beyond Python error logs.
- **Frontend security warnings are advisory**: A user can bypass the acknowledge flow by using the API directly.
- **slowapi defaults**: Uses in-memory storage; no persistence across restarts, no distributed coordination.

## What's Next

Based on the current limitations and the PRD trajectory, v3 priorities should be:

1. **Production deployment** — Docker containerization, HTTPS via reverse proxy (nginx/Caddy), environment-based configuration
2. **Redis-backed job store** — Persistent jobs across restarts, distributed rate limiting, multi-worker support
3. **User authentication** — API key management, session tokens, per-user rate limits instead of per-IP
4. **Enhanced code scanning** — AST-based analysis instead of regex, detection of obfuscated patterns (base64 decode chains, `getattr`/`__builtins__` tricks)
5. **Sandboxed notebook preview** — Run generated notebooks in an isolated environment before delivery to verify they execute safely
6. **Structured logging and audit trail** — JSON-formatted logs, request IDs for tracing, security event alerting
