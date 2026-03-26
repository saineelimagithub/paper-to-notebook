# Sprint v2 — Tasks

## Status: In Progress

---

- [x] Task 1: Add security headers middleware and tighten CORS (P0)
  - Acceptance: Every response includes `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy: default-src 'self'`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`; CORS `allow_headers` changed from `["*"]` to explicit list `["Content-Type", "X-Api-Key"]`; existing tests still pass; new test verifies headers on `/health` response
  - Files: backend/main.py, tests/backend/test_security_headers.py
  - Completed: 2026-03-26 — Added SecurityHeadersMiddleware (5 headers on all responses), tightened CORS allow_headers to explicit list; 5 new tests, 51 total passing; semgrep clean, npm audit clean

---

- [x] Task 2: Enforce 20MB file size limit on uploads (P0)
  - Acceptance: `POST /generate` with a file > 20MB returns HTTP 413 with `{"detail": "PDF exceeds 20MB limit."}`; files under 20MB still work normally; frontend shows file size and disables submit for files > 20MB; tests cover both accept and reject cases
  - Files: backend/main.py, frontend/src/components/PDFUpload.jsx, tests/backend/test_upload_limits.py
  - Completed: 2026-03-26 — Server-side 20MB check returns 413; frontend disables submit + shows red warning for oversized files; 3 new tests, 54 total passing

---

- [x] Task 3: Move API key from form body to X-Api-Key header (P0)
  - Acceptance: `POST /generate` reads API key from `X-Api-Key` request header instead of form field; frontend sends key via `headers: {"X-Api-Key": apiKey}` on the fetch call; old form-body `api_key` field is removed; all existing tests updated; new test verifies 422 when header is missing
  - Files: backend/main.py, frontend/src/components/PDFUpload.jsx, frontend/src/App.jsx, tests/backend/test_integration.py
  - Completed: 2026-03-26 — Backend uses Header() for X-Api-Key; frontend sends via headers; all integration + upload tests updated; 54 total passing

---

- [x] Task 4: Add rate limiting with slowapi (P0)
  - Acceptance: `pip install slowapi` added to requirements.txt; `/generate` limited to 5 requests/minute per IP; `/publish` limited to 10 requests/minute per IP; exceeding limit returns HTTP 429 with `{"detail": "Rate limit exceeded. Try again in X seconds."}`; test verifies 429 after exceeding limit
  - Files: backend/main.py, backend/requirements.txt, tests/backend/test_rate_limiting.py
  - Completed: 2026-03-26 — slowapi with per-IP limits (5/min generate, 10/min publish); custom 429 handler; 3 new tests, 57 total passing

---

- [x] Task 5: Build input sanitizer for PDF text before Gemini (P0)
  - Acceptance: New module `input_sanitizer.py` with `sanitize_paper_text(paper: dict) -> dict` that: (a) strips Unicode control characters (U+200B–U+200F, U+202A–U+202E, U+2060–U+2064, U+FEFF), (b) detects and neutralizes prompt injection patterns — lines containing "ignore previous instructions", "ignore all instructions", "you are now", "new instructions:", "system:", "ADMIN:", or similar role-override phrases are prefixed with `[USER TEXT]:` to disambiguate from real instructions, (c) truncates `full_text` to 12000 chars (enforced here, not just in notebook_generator); returns sanitized copy of paper dict; tests cover each sanitization rule with adversarial examples
  - Files: backend/input_sanitizer.py, backend/notebook_generator.py, tests/backend/test_input_sanitizer.py
  - Completed: 2026-03-26 — Strips control chars, neutralizes 7+ injection patterns, truncates to 12k chars; wired into notebook_generator; 15 new tests, 72 total passing

---

- [x] Task 6: Build post-generation notebook scanner (P0)
  - Acceptance: New module `notebook_scanner.py` with `scan_notebook(cells: list[dict]) -> list[dict]` that inspects every code cell and returns a list of findings, each `{"cell_index": int, "line": int, "pattern": str, "severity": "critical"|"warning", "description": str}`; detects: `os.system`, `subprocess.run/call/Popen`, `eval()`, `exec()`, `__import__()`, `open()` targeting `/etc/`, `.env`, `.ssh`, `~`, `requests.get/post` to non-localhost URLs, `urllib.request`, `socket.connect`, `shutil.rmtree`, `os.remove`; returns empty list if notebook is clean; `generate_notebook()` in notebook_generator.py calls scanner after build and includes findings in return value; tests cover at least 8 distinct malicious patterns
  - Files: backend/notebook_scanner.py, backend/notebook_generator.py, tests/backend/test_notebook_scanner.py
  - Completed: 2026-03-26 — 12 detection rules (os.system, subprocess, eval, exec, __import__, sensitive open, requests, urllib, socket, shutil.rmtree, os.remove); wired into generate_notebook returning 3-tuple; 18 new tests, 90 total passing

---

- [x] Task 7: Integrate scanner warnings into frontend result card (P1)
  - Acceptance: If the backend returns security findings with the `done` SSE event, the ResultCard displays a yellow warning banner listing each finding with cell index and description; if no findings, no banner is shown; warning banner has a "I understand, download anyway" flow — download button is initially replaced by "Review warnings" until user acknowledges; test verifies warning banner renders when findings are present
  - Files: frontend/src/components/ResultCard.jsx, frontend/src/App.jsx, backend/main.py, backend/job_store.py
  - Completed: 2026-03-26 — Added findings field to JobEvent + SSE payload; ResultCard shows yellow warning banner with acknowledge-before-download flow; 90 total passing

---

- [x] Task 8: Replace raw exception leaking with safe error handler (P1)
  - Acceptance: New module `error_handler.py` with `safe_error_message(exc: Exception) -> str` that returns generic user-facing messages: `"Generation failed. Please try again."` for most errors, `"Invalid API key."` for auth errors, `"PDF could not be parsed."` for parsing errors; full exception is logged server-side via Python `logging` at ERROR level with traceback; `_run_generation()` in main.py uses `safe_error_message()` for the SSE error event; test verifies that exception details (file paths, stack traces) never appear in SSE error messages
  - Files: backend/error_handler.py, backend/main.py, tests/backend/test_error_handler.py
  - Completed: 2026-03-26 — Classifies errors into auth/PDF/generic categories; logs full traceback server-side; never leaks paths, keys, or stack traces; 10 new tests, 100 total passing

---

- [x] Task 9: Add TTL-based job cleanup and max concurrent job cap (P1)
  - Acceptance: Background task runs every 60 seconds and evicts jobs older than 30 minutes from the in-memory store; max concurrent jobs capped at 20 — `/generate` returns HTTP 503 `{"detail": "Server busy. Try again shortly."}` when cap is reached; `Job` dataclass gets a `created_at: float` field (time.monotonic); test verifies: old jobs are cleaned up, cap is enforced, active jobs are not evicted
  - Files: backend/job_store.py, backend/main.py, tests/backend/test_job_cleanup.py
  - Completed: 2026-03-26 — TTL cleanup every 60s evicts jobs > 30 min; max 20 concurrent jobs returns 503; created_at field on Job; periodic cleanup via lifespan task; 7 new tests, 107 total passing

---

- [ ] Task 10: Switch Gists to secret and validate job_id as UUID (P2)
  - Acceptance: `gist_publisher.py` changed from `"public": True` to `"public": False`; `/stream/{job_id}` validates that `job_id` matches UUID format (regex or `uuid.UUID()` parse) and returns 400 if invalid; `.gitignore` updated to use global `*.env` pattern (with `!*.env.example` exception); tests verify: gist payload has `public: false`, invalid job_id returns 400, `.env.example` is not gitignored
  - Files: backend/gist_publisher.py, backend/main.py, .gitignore, backend/tests/test_gist_publisher.py, backend/tests/test_integration.py
