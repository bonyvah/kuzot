# Project Overview

An AI-powered Competitive Intelligence (CI) platform designed to automate the tracking, ingestion, and analysis of competitor activities. It continuously monitors competitor digital footprints—such as pricing updates, feature launches, marketing copy, and news—and enables users to perform real-time semantic search and automated intelligence synthesis via Retrieval-Augmented Generation (RAG).

## Core Capabilities

- Automated Web Monitoring: Asynchronous scraping and change detection across competitor websites, press releases, and product documentation.
- Semantic Vector Search: Deep contextual querying across large volumes of unstructured competitor content.
- AI Analysis & Reporting: LLM-driven summarization, positioning comparisons, and trend extraction.

## Tech Stack

Architecture & Patterns: Event-Driven Architecture, Retrieval-Augmented Generation (RAG), Asynchronous Task Processing, RESTful APIs.

Backend: Python, FastAPI, SQLAlchemy, Pydantic.

Frontend: React (TypeScript), Vite, Tailwind CSS, shadcn/ui, Material Symbols (Google icons).

State & Data Fetching: Zustand, TanStack Query, TanStack Router, Axios.

AI & Search: LangChain, LangGraph, MCP, Pinecone (Vector Database), OpenAI APIs.

Observability & Evals: OpenTelemetry, Jaeger (or Langfuse), Promptfoo.

Data Storage: PostgreSQL (App data), MongoDB (unstructured HTML scrapes).

Caching & Message Broker: Redis (Caching), Celery (Distributed Task Queue), RabbitMQ(Task Broker).

Web Scraping: Playwright, Rotating Proxies, Headless Browser Automation.

Auth & Security: Clerk, OAuth2, JWT Authentication, AWS Secrets Manager.

DevOps & Cloud: Docker (Containerization), Nginx (Reverse Proxy & Static Asset Serving), GitHub Actions (CI/CD), Terraform (IaC), AWS (ECS Fargate, ALB, ECR, S3, RDS, ElastiCache).

## Competitor Agent

`POST /api/v1/workspaces/{id}/ask` answers a question using a LangGraph agent (`backend/app/agent/`). Its tools are Pydantic-typed: `search_changes`, `get_page_history` and `compare_pricing`. Prices are parsed from pages by code, not read by the model. Every `[n]` in an answer is checked against what the tools returned. A bad citation gets one retry, then it is removed and `citations_valid` is false.

### MCP server

The same tools are available to any MCP client over stdio. The workspace is fixed by the environment, and tool arguments can't change it. There is no user login: whoever can start the process already holds the database credentials.

```bash
docker compose exec -T -e KUZOT_MCP_WORKSPACE_ID=<workspace-uuid> api python -m app.mcp_server
```

### Tracing

`docker compose up` sends API, Celery and OpenAI spans (model, tokens, latency) to Jaeger at http://localhost:16686. To use Langfuse, see `backend/.env.example`. Tracing is off when `OTEL_EXPORTER_OTLP_ENDPOINT` is unset. Prompts and completions are not recorded unless `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` is set.

### Evals

20 Promptfoo cases in `backend/evals/` run against invented competitors, including a prompt injection in a scraped page. All checks are deterministic: schemas, citations, quoted amounts and exact pricing diffs.

```bash
make evals          # all 20; calls OpenAI
make evals-offline  # the 9 that need no API key
```
