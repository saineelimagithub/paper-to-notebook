# Sprint v3 — Tasks

## Status: In Progress

---

## Area 1: Testing Pyramid

- [x] Task 1: Expand unit tests for pdf_parser and notebook_generator (P0)
  - Acceptance: `pdf_parser` tests cover: empty bytes, corrupt PDF, single-page, multi-page, title extraction by font size, abstract extraction, section heading detection, full_text truncation; `notebook_generator` tests cover: `_parse_json_safe` with valid JSON, invalid backslash escapes, completely broken JSON raises; `build_notebook` with valid cells, empty cells, mixed markdown/code; total new unit tests ≥ 15; all pass with `pytest tests/backend/test_pdf_parser.py tests/backend/test_notebook_generator.py -v`
  - Files: tests/backend/test_pdf_parser.py, tests/backend/test_notebook_generator.py
  - Completed: 2026-03-27 — 24 pdf_parser tests (was 9) + 27 notebook_generator tests (was 21) including _parse_json_safe, _is_section_heading, _extract_structure, build_notebook edge cases; 135 total passing; semgrep clean

---

- [x] Task 2: Expand unit tests for gist_publisher, job_store, and error_handler (P0)
  - Acceptance: `gist_publisher` tests cover: missing GITHUB_TOKEN returns None, title sanitization (special chars stripped), payload structure (`public: false`, filename format), HTTP error raises; `job_store` tests cover: create_job returns Job, get_job returns None for unknown, Job.push/stream round-trip, JobEvent.findings field; `error_handler` tests cover: all three categories + no leakage of paths/keys/tracebacks confirmed with multiple exception types; total new unit tests ≥ 12; all pass
  - Files: tests/backend/test_gist_publisher.py, tests/backend/test_job_store.py, tests/backend/test_error_handler.py
  - Completed: 2026-03-27 — 16 new job_store tests, 4 new gist_publisher tests (HTTP error, timeout, filename, description), 7 new error_handler tests (additional classification + leakage); 160 total passing; semgrep clean

---

- [x] Task 3: Integration tests with mocked Gemini for /generate → /stream flow (P0)
  - Acceptance: New test file `test_api_integration.py` uses `FastAPI TestClient` with `unittest.mock.patch` to mock `genai.Client.models.generate_content` returning a canned JSON response; tests cover: (1) POST /generate with valid PDF + X-Api-Key → 200 + job_id, (2) GET /stream/{job_id} receives SSE events ending in `done` with `notebook_b64` + `colab_url` fields, (3) POST /generate with invalid PDF → 400, (4) POST /generate exceeding rate limit → 429, (5) GET /stream with invalid UUID → 400; at least 5 integration tests; all pass
  - Files: tests/backend/test_api_integration.py
  - Completed: 2026-03-27 — 8 integration tests: full generate→stream flow with mocked Gemini+Gist, valid PDF job_id, invalid PDF 400, rate limit 429, invalid UUID 400, unknown UUID 404, missing API key 422, SSE done event structure; 168 total passing; semgrep clean

---

- [x] Task 4: Playwright E2E tests — full user flow with screenshots (P0)
  - Acceptance: New test file `tests/e2e/full-flow.spec.js` tests: (1) page loads with title "Paper → Notebook", (2) API key input accepts text and masks it, (3) PDF upload via file chooser shows filename, (4) clicking Generate shows progress display, (5) eventually reaches result card OR error state; screenshots saved to `tests/screenshots/` at each step: `e2e-01-page-loaded.png`, `e2e-02-api-key-entered.png`, `e2e-03-pdf-selected.png`, `e2e-04-generating.png`, `e2e-05-result.png`; update `playwright.config.js` to save screenshots to `tests/screenshots/`; backend mock not required (test can use a fake API key and expect an error state gracefully); test passes in headless mode
  - Files: tests/e2e/full-flow.spec.js, playwright.config.js
  - Completed: 2026-03-27 — 5 Playwright E2E tests: page load, API key masking, PDF upload filename, generate→result/error flow, idle state; 6 screenshots at each step; playwright.config.js updated with testIgnore for @live tests; npm audit clean

---

- [x] Task 5: Live quality test — real Gemini call with "Attention Is All You Need" (P1)
  - Acceptance: New test file `tests/e2e/live-quality.spec.js` with `headed: true` (visible browser); test: (1) navigates to localhost:5173, (2) enters a real Gemini API key from env var `GEMINI_API_KEY`, (3) uploads `C:\Users\U6041256\Downloads\NIPS-2017-attention-is-all-you-need-Paper.pdf`, (4) clicks Generate, (5) waits up to 120s for result card, (6) clicks Download, (7) reads downloaded `.ipynb` file and validates: valid JSON, has `cells` array, ≥ 8 cells, at least one code cell contains `import`, at least one markdown cell contains `#`; screenshots at each step saved to `tests/screenshots/live-*`; test is tagged `@live` so it doesn't run in CI (only manually); passes when run with `npx playwright test tests/e2e/live-quality.spec.js --headed`
  - Files: tests/e2e/live-quality.spec.js
  - Completed: 2026-03-27 — Live quality test with 7 screenshot steps; auto-skips when GEMINI_API_KEY not set; validates: valid JSON, cells array, ≥8 cells, code cells with import, markdown cells with #; handles security warning acknowledge flow; 3-min timeout

---

## Area 2: CI/CD Pipeline

- [x] Task 6: Install GitHub CLI and create remote repository (P0)
  - Acceptance: `gh` CLI is installed and authenticated (`gh auth status` succeeds); a new GitHub repo is created (public or private, user's choice) via `gh repo create`; local repo has `origin` remote pointing to the new GitHub repo; all existing code is pushed to `main` branch; `gh repo view` shows the repo
  - Files: (no code files — CLI operations only)
  - Completed: 2026-03-28 — Installed gh 2.89.0 via winget; authenticated as saineelimagithub; created public repo saineelimagithub/paper-to-notebook; pushed all code to origin/master

---

- [x] Task 7: GitHub Actions CI workflow — tests + security scans (P0)
  - Acceptance: New file `.github/workflows/ci.yml` with a workflow that triggers on `push` and `pull_request` to `main`; jobs: (1) `backend-tests` — sets up Python 3.12, installs requirements.txt + pytest, runs `pytest tests/backend/ -v`, (2) `e2e-tests` — sets up Node 20, installs frontend deps + Playwright, starts backend + frontend, runs `npx playwright test` (excludes `@live` tagged tests), uploads `tests/screenshots/` as artifact, (3) `security-scan` — runs `semgrep --config auto backend/ frontend/src/ --quiet` and `pip-audit -r backend/requirements.txt`; all three jobs must pass for PR checks to be green; workflow pushed to GitHub; `gh run list` shows the workflow
  - Files: .github/workflows/ci.yml
  - Completed: 2026-03-28 — 3-job CI workflow: backend-tests (pytest), e2e-tests (Playwright + screenshot artifacts), security-scan (semgrep + pip-audit + npm audit); triggers on push/PR to master/main

---

- [ ] Task 8: Branch protection — block merge if checks fail (P0)
  - Acceptance: Branch protection rule on `main` requires: (1) all CI status checks to pass (`backend-tests`, `e2e-tests`, `security-scan`), (2) at least 0 approvals (solo developer); configured via `gh api` or `gh` CLI; verified by creating a test branch with a failing test, pushing, and confirming the PR shows "checks failing — merge blocked"
  - Files: (no code files — GitHub API operations only)

---

## Area 3: Docker & Cloud Deployment

- [ ] Task 9: Dockerfiles for backend and frontend + docker-compose.yml (P0)
  - Acceptance: `backend/Dockerfile` — Python 3.12-slim base, copies requirements.txt, pip install, copies source, exposes 8000, CMD `uvicorn main:app --host 0.0.0.0 --port 8000`; `frontend/Dockerfile` — two-stage: Node 20-alpine build stage runs `npm ci && npm run build`, nginx:alpine serve stage copies `dist/` to `/usr/share/nginx/html/` and copies custom `nginx.conf`; `frontend/nginx.conf` — serves static files on port 80, proxies `/generate`, `/stream`, `/publish`, `/health` to `backend:8000`; `docker-compose.yml` at project root defines `backend` and `frontend` services on a shared network, frontend depends_on backend; `docker compose up --build` starts both and `curl http://localhost/health` returns `{"status": "ok"}`; `docker compose down` cleans up
  - Files: backend/Dockerfile, frontend/Dockerfile, frontend/nginx.conf, docker-compose.yml

---

- [ ] Task 10: Terraform config for AWS ECS Fargate + CD pipeline (P1)
  - Acceptance: `terraform/` directory with: `backend.tf` (S3 remote state bucket), `variables.tf` (region, image tags, env vars for GITHUB_TOKEN), `main.tf` (VPC default, ECR repos for backend + frontend, ECS cluster, task definition with both containers, ECS service with ALB, security groups allowing port 80 inbound, CloudWatch log group), `outputs.tf` (ALB DNS name); new file `.github/workflows/cd.yml` — triggers on push to `main` after CI passes; steps: (1) configure AWS credentials from GitHub Secrets `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`, (2) login to ECR, (3) build + tag + push backend and frontend images, (4) force new ECS deployment via `aws ecs update-service --force-new-deployment`; AWS credentials stored as GitHub repo secrets (NOT committed to code); `terraform plan` runs without errors locally
  - Files: terraform/backend.tf, terraform/variables.tf, terraform/main.tf, terraform/outputs.tf, .github/workflows/cd.yml
