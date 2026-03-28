# Sprint v3 — Walkthrough

## Summary
Sprint v3 made the Paper → Notebook Generator production-ready across three pillars: a comprehensive testing pyramid (168 backend tests + 5 E2E tests + 1 live quality test), a GitHub Actions CI/CD pipeline that gates every merge with automated tests and security scans, and full Docker containerization with Terraform-managed AWS ECS Fargate deployment. The app was successfully deployed to AWS and served live traffic at `paper-to-notebook-*.us-east-1.elb.amazonaws.com` before infrastructure was torn down to avoid costs.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        GitHub (saineelimagithub/paper-to-notebook)       │
│                                                                         │
│  Push/PR ──▶ CI Workflow (.github/workflows/ci.yml)                     │
│               ├─ backend-tests (pytest, 168 tests)                      │
│               ├─ e2e-tests (Playwright, 5 tests + screenshots)          │
│               └─ security-scan (semgrep + pip-audit + npm audit)        │
│                                                                         │
│  Merge ──▶ CD Workflow (.github/workflows/cd.yml)                       │
│             ├─ Build Docker images (backend + frontend)                  │
│             ├─ Push to ECR                                              │
│             └─ Force new ECS deployment                                 │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     AWS (Terraform-managed, us-east-1)                   │
│                                                                         │
│  ┌────────┐    ┌──────────────────────────────────────────────────┐     │
│  │  ALB   │───▶│           ECS Fargate Task                       │     │
│  │ :80    │    │  ┌──────────────┐      ┌─────────────────────┐  │     │
│  │        │    │  │   frontend   │      │      backend        │  │     │
│  │        │    │  │ nginx:alpine │ ───▶ │ python:3.12-slim    │  │     │
│  │        │    │  │   :80       │ proxy │ uvicorn :8000       │  │     │
│  └────────┘    │  └──────────────┘      └─────────────────────┘  │     │
│                └──────────────────────────────────────────────────┘     │
│                                                                         │
│  ┌──────┐  ┌────────────┐  ┌───────────┐  ┌──────────────────────┐    │
│  │ ECR  │  │ CloudWatch │  │ S3 (state)│  │ Security Groups      │    │
│  └──────┘  └────────────┘  └───────────┘  └──────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘

Testing Pyramid:
                    ┌───────────┐
                    │  1 Live   │  Real Gemini + "Attention Is All You Need"
                    ├───────────┤
                    │   5 E2E   │  Playwright (headless, screenshots)
                    ├───────────┤
                    │ 8 Integr. │  FastAPI TestClient, mocked Gemini
                    ├───────────┤
                    │  155 Unit │  pytest (all backend modules)
                    └───────────┘
```

## Files Created/Modified

### tests/backend/test_pdf_parser.py
**Purpose**: Unit tests for the PDF parsing module — expanded from 9 to 24 tests.
**Key Tests**:
- `test_empty_bytes_raises` — Empty/None bytes produce a graceful error
- `test_title_by_largest_font` — Title extraction uses largest font size on first page
- `test_is_section_heading_*` — Section heading detection (numbered, named, ALL CAPS, rejection)
- `test_extract_structure_*` — Multi-section end-to-end parsing

**How it works**:
The original 9 tests covered basic PDF parsing. Sprint v3 added 15 new tests covering edge cases — corrupt PDFs, single vs. multi-page, abstract extraction, the `_is_section_heading()` helper with various heading formats, and the `_extract_structure()` pipeline that chains all stages together. Tests use PyMuPDF (`fitz`) to generate minimal PDFs in memory, avoiding dependency on fixture files.

---

### tests/backend/test_notebook_generator.py
**Purpose**: Unit tests for notebook generation — expanded from 21 to 27 tests.
**Key Tests**:
- `test_parse_json_safe_*` — JSON repair for Gemini's invalid LaTeX backslash escapes
- `test_build_notebook_*` — nbformat assembly: single types, unknown type skipped, serializable
- `test_generate_notebook_*` — Sanitizer integration, suspicious code findings

**How it works**:
The critical addition is testing `_parse_json_safe()`, which handles a real production bug: Gemini returns JSON containing LaTeX like `\section`, `\epsilon` which are invalid JSON escapes. The function tries `json.loads()` first, and on failure applies a regex repair:

```python
_INVALID_ESCAPE = re.compile(r'\\(?!["\\/bfnrtu])')

def _parse_json_safe(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        repaired = _INVALID_ESCAPE.sub(r'\\\\', text)
        return json.loads(repaired)
```

Tests verify: valid JSON passes through, nested structures preserved, invalid escapes repaired, valid escapes like `\n` left untouched, completely broken JSON still raises.

---

### tests/backend/test_job_store.py
**Purpose**: 16 unit tests for the in-memory job store.
**Key Tests**:
- `test_job_event_defaults` — JobEvent has sensible defaults for optional fields
- `test_job_push_stream_roundtrip` — Push events and stream them back in order
- `test_stream_stops_on_done` — Streaming terminates after a `done` event
- `test_capacity_cap` — Job store enforces MAX_JOBS limit

**How it works**:
The job store uses an asyncio Queue per job. `push()` adds events, `stream()` yields them as an async generator. Tests verify the full lifecycle: creation, event push/stream round-trip, terminal states (done/error) stopping the stream, and capacity limits. The `_jobs` dict is cleared before each test via `setup_function()`.

---

### tests/backend/test_gist_publisher.py
**Purpose**: Expanded from 7 to 11 tests for GitHub Gist publishing.
**Key New Tests**:
- `test_http_error_propagation` — httpx errors bubble up correctly
- `test_timeout_30s` — HTTP timeout is set to 30 seconds
- `test_filename_format` — Gist filename matches expected pattern
- `test_description_includes_title` — Gist description contains the paper title

---

### tests/backend/test_error_handler.py
**Purpose**: Expanded from 10 to 17 tests for safe error message handling.
**Key New Tests**:
- Additional error classification variants (auth, PDF, connection errors)
- Leakage checks confirming no file paths, API keys, or tracebacks in user-facing messages

---

### tests/backend/test_api_integration.py
**Purpose**: 8 integration tests covering the full `/generate` → `/stream` API flow with mocked Gemini.
**Key Tests**:
- `test_generate_and_stream_full_flow` — Full pipeline: upload PDF → mocked Gemini → SSE events → done with notebook_b64
- `test_generate_rate_limit_returns_429` — 6th request within a minute triggers rate limiting
- `test_sse_done_event_structure` — Done event contains all required fields (type, message, elapsed, notebook_b64, colab_url, findings)

**How it works**:
Tests use `FastAPI TestClient` with `unittest.mock.patch` to intercept two external calls: (1) `notebook_generator.genai` (the Gemini client) returns a canned JSON response with 7 cells, and (2) `gist_publisher.httpx.post` (the GitHub API) returns a fake gist ID. This lets the full pipeline run without real API keys:

```python
with patch("notebook_generator.genai") as mock_genai, \
     patch("gist_publisher.httpx.post") as mock_gist_post:
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _mock_gemini()
    mock_genai.Client.return_value = mock_client
    # ... test the full flow
```

A `reset_state()` fixture clears the job store and rate limiter between tests.

---

### tests/e2e/full-flow.spec.js
**Purpose**: 5 Playwright E2E tests covering the full browser user flow.
**Key Tests**:
- Step 1: Page loads with "Paper → Notebook" heading
- Step 2: API key input accepts text and masks it (password type)
- Step 3: PDF upload shows filename in the drop zone
- Step 4: Clicking Generate shows progress, then result card or error
- Step 5: Idle state has API key input and drop zone visible

**How it works**:
Tests run in headless Chromium via Playwright. A helper `createMinimalPdfBuffer()` generates a tiny valid PDF in memory (no fixture files needed). Screenshots are captured at each step to `tests/screenshots/e2e-*.png` and uploaded as GitHub Actions artifacts. Tests use `data-testid` selectors for reliability:

```javascript
const apiKeyInput = page.locator('[data-testid="api-key-input"]');
await apiKeyInput.fill("AIzaSyB-test-key-12345");
const inputType = await apiKeyInput.getAttribute("type");
expect(inputType).toBe("password");
```

---

### tests/e2e/live-quality.spec.js
**Purpose**: Live quality test that generates a REAL notebook from "Attention Is All You Need" using an actual Gemini API key.
**Key Validations**:
- Downloaded `.ipynb` is valid JSON
- Has `cells` array with ≥ 8 cells
- At least one code cell contains `import`
- At least one markdown cell contains `#`

**How it works**:
This test auto-skips when `GEMINI_API_KEY` env var is not set, so it never runs in CI. When run manually with `--headed`, it opens a visible browser, enters the real API key, uploads the Attention paper PDF, waits up to 120 seconds for the result, downloads the notebook, and validates its structure. Screenshots are saved at 7 steps for evidence. The test confirmed the app produces a 14-cell notebook with 10 code cells and 4 markdown cells.

---

### playwright.config.js
**Purpose**: Playwright test configuration.
**Key Settings**:
- `testDir: "./tests/e2e"` — E2E test directory
- `timeout: 60_000` — 60-second default timeout per test
- `baseURL: "http://localhost:5173"` — Vite dev server
- `headless: true` — Runs without visible browser in CI
- `webServer` config auto-starts the Vite frontend

---

### .github/workflows/ci.yml
**Purpose**: CI pipeline — runs on every push/PR to master/main.
**Jobs**:
- `backend-tests` — Python 3.12, installs requirements + pytest-asyncio, runs `pytest tests/backend/ -v`
- `e2e-tests` — Node 20 + Python 3.12, starts backend (uvicorn) + frontend (Vite), runs Playwright, uploads screenshot artifacts
- `security-scan` — semgrep static analysis, pip-audit dependency scan, npm audit

**How it works**:
Three parallel jobs that all must pass for a PR to be mergeable. The E2E job is the most complex — it spins up the full stack in CI:

```yaml
- name: Start backend
  run: |
    cd backend
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
    sleep 3
    curl -f http://localhost:8000/health
```

Screenshots are always uploaded (even on failure) via `actions/upload-artifact@v4` with 7-day retention.

---

### .github/workflows/cd.yml
**Purpose**: CD pipeline — auto-deploys to AWS ECS on push to master/main.
**Steps**:
1. Configure AWS credentials from GitHub Secrets
2. Login to Amazon ECR
3. Build, tag (commit SHA + latest), and push backend image
4. Build, tag, and push frontend image
5. Force new ECS deployment via `aws ecs update-service --force-new-deployment`

**How it works**:
Each image is tagged with both the git commit SHA (for traceability) and `latest` (for the ECS task definition). The force-new-deployment flag tells ECS to pull the latest images and perform a rolling update. AWS credentials are stored as GitHub Secrets — never committed to code.

---

### backend/Dockerfile
**Purpose**: Container image for the FastAPI backend.

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libmupdf-dev
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Installs `libmupdf-dev` for PyMuPDF's native PDF parsing. The `.dockerignore` excludes `__pycache__`, `.venv`, and `.env`.

---

### frontend/Dockerfile
**Purpose**: Two-stage build for the React frontend — Node builds, nginx serves.

Stage 1 (build): `node:20-alpine` runs `npm ci && npm run build` to produce static assets in `/app/dist`.

Stage 2 (serve): `nginx:alpine` copies the built assets and an nginx config template. At startup, `sed` replaces the `BACKEND_UPSTREAM` placeholder with the actual backend host:

```dockerfile
ENV BACKEND_HOST=localhost
CMD sh -c "sed 's|BACKEND_UPSTREAM|'\"$BACKEND_HOST\"':8000|g' \
    /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf \
    && nginx -g 'daemon off;'"
```

This allows the same image to work in ECS (`localhost` — both containers in same task) and Docker Compose (`backend` — service name DNS).

---

### frontend/nginx.conf
**Purpose**: Nginx configuration for serving the React SPA and proxying API requests.
**Key Sections**:
- `location ~ ^/(generate|stream|publish|health)` — Proxies API routes to the backend with SSE support (`proxy_buffering off`, `proxy_read_timeout 300s`)
- `location /` — SPA fallback via `try_files $uri $uri/ /index.html`

---

### docker-compose.yml
**Purpose**: Local development stack — runs both services on a shared network.
**Services**:
- `backend` — Builds from `./backend`, exposes port 8000, passes `GITHUB_TOKEN` env var
- `frontend` — Builds from `./frontend`, exposes port 80, sets `BACKEND_HOST=backend`, depends_on backend

---

### terraform/backend.tf
**Purpose**: Terraform provider config and S3 remote state backend.
**Key Config**: State stored in `s3://paper-to-notebook-tfstate/prod/terraform.tfstate`.

---

### terraform/variables.tf
**Purpose**: Input variables for the Terraform configuration.
**Variables**: `aws_region` (default: us-east-1), `backend_image_tag`, `frontend_image_tag`, `github_token` (sensitive).

---

### terraform/main.tf
**Purpose**: Core AWS infrastructure — 13 resources.
**Resources**:
- `aws_ecr_repository` (x2) — Backend and frontend image registries
- `aws_ecs_cluster` — Fargate cluster named `paper-to-notebook`
- `aws_ecs_task_definition` — Both containers in one task (0.5 vCPU, 1GB RAM)
- `aws_ecs_service` — Desired count 1, Fargate launch type, public IP
- `aws_lb` + `aws_lb_listener` + `aws_lb_target_group` — ALB on port 80 with 300s idle timeout
- `aws_security_group` (x2) — ALB allows port 80 inbound; ECS allows traffic only from ALB
- `aws_iam_role` + `aws_iam_role_policy_attachment` — ECS task execution role
- `aws_cloudwatch_log_group` — 14-day log retention

---

### terraform/outputs.tf
**Purpose**: Terraform outputs for post-apply reference.
**Outputs**: `alb_dns_name`, `backend_ecr_url`, `frontend_ecr_url`.

---

### backend/notebook_generator.py (modified)
**Purpose**: Three production fixes applied during v3.
**Changes**:
1. **`_parse_json_safe()`** — JSON repair function for Gemini's invalid LaTeX escapes (added in v3 Task 1)
2. **`http_options={"timeout": 300_000}`** — 5-minute timeout on Gemini client (fixed "Generation failed" error for large papers)
3. **SSE keepalive** — Async task sends progress events every 15 seconds during the Gemini API call to prevent ALB idle timeout disconnects:

```python
async def _keepalive():
    messages = ["Generating code implementations...", ...]
    i = 0
    while True:
        await asyncio.sleep(15)
        await progress(messages[i % len(messages)])
        i += 1

keepalive_task = asyncio.create_task(_keepalive())
try:
    response = await asyncio.to_thread(client.models.generate_content, ...)
finally:
    keepalive_task.cancel()
```

---

### .gitignore (modified)
**Purpose**: Added entries for `test-results/`, `aws_cred*`, `*.credentials`, `*.pem` to prevent accidental credential commits.

## Data Flow

### CI Pipeline (every push/PR)
1. Developer pushes code → GitHub Actions triggers CI workflow
2. Three parallel jobs run: pytest (168 tests), Playwright (5 E2E tests + screenshots), security scan (semgrep + pip-audit + npm audit)
3. All three must pass → branch protection blocks merge if any fail
4. Screenshots uploaded as artifacts for visual review

### CD Pipeline (merge to master)
1. Push to master → CD workflow triggers
2. AWS credentials loaded from GitHub Secrets
3. Backend + frontend Docker images built, tagged with commit SHA + `latest`
4. Images pushed to ECR
5. `aws ecs update-service --force-new-deployment` → ECS pulls new images → rolling update

### Live Request Flow (on AWS)
1. User visits ALB DNS → nginx serves React SPA
2. User enters Gemini API key + uploads PDF → POST `/generate` proxied to backend
3. Backend returns `job_id`, starts background task
4. Frontend opens SSE connection → GET `/stream/{job_id}` proxied to backend
5. Backend: parse PDF → call Gemini (with 15s keepalive events) → build notebook → publish Gist
6. SSE `done` event with `notebook_b64` + `colab_url` → frontend shows result card
7. User downloads `.ipynb` or opens in Colab

## Test Coverage

- **Unit: 155 tests** — pdf_parser (24), notebook_generator (27), notebook_scanner (12), input_sanitizer (10), error_handler (17), job_store (16), gist_publisher (11), security_headers (8), upload_limits (7), rate_limiting (6), job_cleanup (5), integration (old, 12)
- **Integration: 8 tests** — Full /generate → /stream flow with mocked Gemini, error codes (400, 404, 422, 429), SSE event structure
- **E2E: 5 tests** — Page load, API key masking, PDF upload, generate flow, idle state (Playwright, headless Chromium)
- **Live: 1 test** — Real Gemini call with "Attention Is All You Need", validates 14-cell notebook structure (manual only, skipped in CI)
- **Total: 168 backend + 5 E2E + 1 live = 174 tests**

## Security Measures

- **CI security scans**: semgrep static analysis + pip-audit + npm audit on every push
- **Branch protection**: All 3 CI checks must pass before merge to master
- **No credentials in code**: AWS keys stored as GitHub Secrets, `.gitignore` blocks `aws_cred*` files
- **Docker security**: `.dockerignore` excludes `.env`, `__pycache__`, `node_modules`
- **Network isolation**: ECS security group only allows traffic from ALB (no direct container access)
- **Existing v2 hardening**: Input sanitization, notebook scanning, safe error messages, rate limiting, security headers, CORS restrictions (all carried forward)

## Known Limitations

- **No HTTPS**: ALB serves HTTP only — needs ACM certificate + HTTPS listener for production
- **No custom domain**: Accessible only via auto-generated ALB DNS name
- **In-memory job store**: Jobs are lost on container restart — needs Redis or DynamoDB for durability
- **Single task (no auto-scaling)**: Fixed `desired_count = 1` — no scaling policy for traffic spikes
- **No monitoring/alerting**: CloudWatch Logs exist but no dashboards or alarms configured
- **Docker Compose untested locally**: Docker Desktop was not installed, so `docker compose up` was not verified
- **ALB idle timeout workaround**: 300s timeout + SSE keepalive is a workaround; proper solution would be streaming Gemini responses
- **No user authentication**: Anyone with the URL can use the app (relies on users providing their own Gemini API key)

## What's Next

v4 should focus on production hardening and operational maturity:

1. **HTTPS + Custom Domain** — ACM certificate, Route53 DNS, ALB HTTPS listener
2. **Persistent Job Store** — Redis or DynamoDB to survive container restarts
3. **Auto-scaling** — ECS service auto-scaling based on CPU/request count
4. **Monitoring** — CloudWatch dashboards, alarms for error rates and latency
5. **Streaming Gemini** — Use Gemini's streaming API to send real-time progress instead of keepalive hacks
6. **User Authentication** — OAuth or API key management for access control
7. **Cost Optimization** — Spot Fargate tasks, ALB idle scaling, or Lambda alternative
