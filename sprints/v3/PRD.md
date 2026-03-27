# Sprint v3 — PRD: Production-Ready (Testing, CI/CD, Docker & Cloud)

## Overview
Make the Paper → Notebook Generator production-ready across three pillars: comprehensive testing (pyramid: unit → integration → E2E → live quality), a GitHub Actions CI/CD pipeline that gates every merge, and Docker + AWS ECS Fargate deployment with Terraform. After this sprint, every push runs automated tests + security scans, and merges to `main` trigger auto-deployment to AWS.

## Goals
- Test pyramid in place: ~70% unit, ~20% integration, ~10% E2E — covering all backend modules with mocked Gemini
- Playwright E2E tests cover the full user flow (enter key → upload PDF → progress → download) with screenshots at each step
- A live quality test opens a visible browser, generates a real notebook from "Attention Is All You Need", and validates output structure
- GitHub Actions CI runs pytest, Playwright, semgrep, and pip-audit on every push/PR — blocks merge on failure
- Docker Compose runs the full stack locally (`docker compose up`)
- Terraform provisions AWS ECS Fargate; CD pipeline auto-deploys on merge to main

## User Stories
- As a developer, I want comprehensive tests so that refactoring doesn't break existing behavior
- As a developer, I want CI to catch regressions before merge so that main is always green
- As a reviewer, I want Playwright screenshots in CI artifacts so that I can visually verify UI behavior
- As an operator, I want `docker compose up` to start the full stack so that deployment is reproducible
- As an operator, I want merges to main to auto-deploy to AWS so that releases require no manual steps
- As a researcher, I want confidence that generated notebooks are structurally valid and contain real Python code

## Technical Architecture

### Tech Stack
- **Existing**: FastAPI, React 18 + Vite + Tailwind, PyMuPDF, Gemini 2.5 Flash, nbformat, slowapi
- **New — Testing**: pytest + pytest-asyncio, Playwright (Chromium), unittest.mock
- **New — CI/CD**: GitHub Actions, GitHub CLI (`gh`)
- **New — Containers**: Docker multi-stage builds, nginx (frontend), docker-compose
- **New — Cloud**: Terraform, AWS ECS Fargate, ECR, ALB, CloudWatch Logs, S3 (Terraform state)

### Architecture Diagram
```
┌─────────────────────────────────────────────────────────────────────┐
│                        GitHub Repository                            │
│                                                                     │
│  Push / PR ──▶ GitHub Actions CI                                    │
│                 ├─ pytest (unit + integration)                       │
│                 ├─ Playwright (E2E + screenshots)                    │
│                 ├─ semgrep (static analysis)                         │
│                 └─ pip-audit (dependency scan)                       │
│                                                                     │
│  Merge to main ──▶ CD Pipeline                                      │
│                     ├─ Build Docker images                           │
│                     ├─ Push to ECR                                   │
│                     └─ Deploy to ECS Fargate                         │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     AWS (Terraform-managed)                          │
│                                                                     │
│  ┌─────────────┐    ┌─────────────────────────────────────────┐     │
│  │     ALB      │───▶│          ECS Fargate Cluster            │     │
│  │  (port 80)   │    │                                         │     │
│  └─────────────┘    │  ┌─────────────┐  ┌─────────────────┐  │     │
│                      │  │  Frontend   │  │    Backend       │  │     │
│                      │  │  (nginx     │  │  (uvicorn        │  │     │
│                      │  │   :80)      │  │   :8000)         │  │     │
│                      │  └─────────────┘  └─────────────────┘  │     │
│                      └─────────────────────────────────────────┘     │
│                                                                     │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────────────┐      │
│  │   ECR    │  │  CloudWatch  │  │  S3 (Terraform state)    │      │
│  │ (images) │  │   (logs)     │  │                          │      │
│  └──────────┘  └──────────────┘  └──────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

### Docker Layout
```
project/
├── backend/
│   └── Dockerfile          # Python 3.12-slim, pip install, uvicorn
├── frontend/
│   └── Dockerfile          # Node build stage → nginx serve stage
├── docker-compose.yml      # backend:8000 + frontend:80, shared network
├── nginx.conf              # Frontend: serve static + proxy /api → backend
└── terraform/
    ├── main.tf             # ECS cluster, task def, service, ALB
    ├── variables.tf        # Region, image tags, env vars
    ├── outputs.tf          # ALB URL, cluster ARN
    └── backend.tf          # S3 remote state
```

### Testing Pyramid
```
                    ┌───────────┐
                    │    E2E    │  ~10% — Playwright browser tests
                    │ (visible  │  Full user flow + screenshot evidence
                    │  + headless│
                    ├───────────┤
                    │Integration│  ~20% — FastAPI TestClient
                    │(mocked    │  Full endpoint wiring, mocked Gemini
                    │ Gemini)   │
                    ├───────────┤
                    │   Unit    │  ~70% — pytest
                    │ (all      │  pdf_parser, input_sanitizer,
                    │  modules) │  notebook_scanner, error_handler,
                    │           │  notebook_generator, job_store,
                    │           │  gist_publisher, JSON repair
                    └───────────┘
```

### CI/CD Flow
```
Push/PR ──▶ GitHub Actions ──▶ ┌─ pytest (unit + integration)
                                ├─ Playwright (E2E, headless)
                                ├─ semgrep --config auto
                                └─ pip-audit
                                     │
                                  All pass? ──No──▶ Block merge ❌
                                     │
                                    Yes
                                     │
                            Merge to main ──▶ CD job
                                               ├─ docker build (backend + frontend)
                                               ├─ docker push → ECR
                                               └─ aws ecs update-service → Fargate
                                                    │
                                                  Live ✅
```

## Out of Scope (v4+)
- HTTPS/TLS termination (use ALB HTTP for now; add ACM cert in v4)
- Custom domain name + Route53
- Redis-backed job store / rate limiting
- User authentication / accounts
- Auto-scaling policies (fixed task count = 1 for now)
- Multi-region deployment
- Monitoring dashboards / alerting (CloudWatch Logs only)
- Database (still in-memory job store)

## Dependencies
- Sprint v1 (core app) + Sprint v2 (security hardening) complete
- GitHub CLI (`gh`) installed and authenticated
- AWS IAM user `paper-to-notebook-deploy` with policies: AmazonEC2FullAccess, AmazonECS_FullAccess, AmazonEC2ContainerRegistryFullAccess, ElasticLoadBalancingFullAccess, IAMFullAccess, CloudWatchLogsFullAccess, AmazonS3FullAccess
- AWS credentials available (stored securely, added as GitHub Secrets)
- Docker Desktop installed locally
- "Attention Is All You Need" PDF at `C:\Users\U6041256\Downloads\NIPS-2017-attention-is-all-you-need-Paper.pdf`
