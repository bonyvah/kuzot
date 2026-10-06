# Kuzot — Project Plan
### AI-Powered Competitive Intelligence Platform

---

## Project Overview

Kuzot is a multi-tenant platform that helps businesses automatically monitor their
competitors' websites, detect changes, and generate AI-powered intelligence reports using
Retrieval-Augmented Generation (RAG).

Users can create workspaces, add competitor websites to monitor, and receive automated
analysis of changes — such as pricing updates, product launches, or blog announcements —
delivered through a semantic search interface and natural language AI reports.

---

## Core Features

- **User & Organization Management** — Multi-user accounts with role-based access control (owner, admin, member) and support for both personal and team workspaces
- **Competitor Monitoring** — Add and manage competitor URLs with configurable automated scraping schedules
- **Intelligent Scraping** — Headless browser automation to handle modern JavaScript-heavy websites, with change detection
- **AI Embedding Pipeline** — Automatic vectorization of scraped content for semantic search
- **RAG-Based Reports** — Natural language AI reports generated from competitor data using Retrieval-Augmented Generation
- **Billing & Plans** — Tiered subscription plans (Free, Individual, Team)
- **Cloud Deployment** — Full production deployment on AWS with infrastructure-as-code

---

## Technology Stack

| Area | Technologies |
|---|---|
| Backend | Python, FastAPI, PostgreSQL, MongoDB |
| Authentication | JWT with rotating refresh tokens, Argon2id password hashing |
| AI & Search | OpenAI, LangChain, Pinecone (Vector Database) |
| Background Processing | Celery, RabbitMQ |
| Caching | Redis |
| Web Scraping | Playwright (headless browser) |
| Frontend | React, TypeScript, Vite |
| Cloud & DevOps | AWS (ECS, RDS, ElastiCache, S3), Docker, Terraform, GitHub Actions, Nginx (Reverse Proxy & Static Asset Serving) |
| Local AWS Emulation | LocalStack — full AWS emulation with IAM enforcement |
| Payments | Finik (Kyrgyzstan) & Stripe (World)|

---

## 13-Week Plan

### Week 1 — Project Foundation
Set up the complete development environment including all databases, message broker, Nginx reverse proxy, and
containerized infrastructure. Configure LocalStack for local
AWS service emulation with IAM enforcement enabled — ensuring permission policies are
correct before ever touching real AWS. Define the full database schema covering users,
organizations, workspaces, competitors, and monitoring records.

**Deliverable:** All infrastructure running locally via Docker and LocalStack; complete database design finalized.

---

### Week 2 — Authentication System
Implement a secure, production-grade authentication system with user registration and login,
JWT-based session management with rotating refresh tokens, and role-based access control
for organization membership.

**Deliverable:** Fully working auth API — register, login, token refresh, and logout with security best practices.

---

### Week 3 — Core Data API
Build the main business logic API covering organization creation, workspace management,
and competitor CRUD operations. Implement data validation, error handling, and pagination.

**Deliverable:** REST API for managing organizations, workspaces, and competitors.

---

### Week 4 — Monitoring & URL Management
Implement the monitored URL system where users configure which competitor pages to track
and at what frequency. Build the scrape job tracking system and integrate Redis caching for
high-traffic endpoints.

**Deliverable:** URL management API with configurable scraping schedules and job history.

---

### Week 5 — Automated Scraping Pipeline
Build the background worker system using Celery and RabbitMQ. Implement headless browser
scraping with Playwright for JavaScript-heavy websites. Apply DOM content extraction to
strip dynamic boilerplate (ads, navigation, timestamps) down to clean article text before
computing content hashes — ensuring change detection fires only on meaningful content
updates, not re-rendered page noise. Changes trigger the downstream AI pipeline automatically.

**Deliverable:** End-to-end automated scraping — from scheduled trigger to reliable change detection and MongoDB storage.

---

### Week 6 — AI Embedding Pipeline
Build the content vectorization pipeline that processes scraped text through chunking,
OpenAI embeddings generation, and storage in the Pinecone vector database. Implement
proper multi-tenant isolation so each organization's data is kept separate.

**Deliverable:** Automated pipeline that populates Pinecone with searchable vector embeddings after every detected change.

---

### Week 7 — RAG Reports & Semantic Search
Implement the AI intelligence layer — semantic search across all competitor content using
vector similarity, and GPT-powered report generation that synthesizes competitor changes
into natural language summaries with source attribution.

**Deliverable:** Working semantic search API and AI report generation endpoint.

---

### Week 8 — Frontend Foundation & Authentication
Initialize the React + TypeScript frontend with routing, state management, and API
integration layer. Build authentication pages (login, registration) and implement
automatic token refresh for seamless user sessions.

**Deliverable:** Frontend application running with working login, registration, and protected routing.

---

### Week 9 — Frontend Core Dashboard
Build the main product interface — workspace dashboard, competitor management, monitored
URL configuration, and scrape job history with live status updates.

**Deliverable:** Fully functional core product UI that users can navigate and operate.

---

### Week 10 — Frontend AI Features
Build the AI-facing interface — semantic search with filtering by competitor and content type,
AI report generation with prompt input, and report viewing with source attribution showing
which competitor data informed each conclusion.

**Deliverable:** Search and report generation UI working end-to-end with the backend AI pipeline.

---

### Week 11 — Billing & Subscription Plans
Implement tiered plan enforcement (Free, Individual, Team) with feature limits. Integrate dual payment providers using a strategy pattern: Stripe (Test Mode) for international USD card billing and a contract-compliant Finik service (mock adapter) for domestic KGS QR payments. Implement secure webhook handling with signature verification, idempotency controls, and automatic plan upgrades.

**Deliverable:** Working billing system with multi-provider payment integration (Stripe & Finik) and plan-based feature gating.

---

### Week 12 — Cloud Deployment & CI/CD
Set up GitHub Actions for automated testing and Docker image building. Deploy the application using a production Docker Compose configuration on a cloud VPS featuring **Nginx for SSL termination, reverse proxy routing, and static frontend serving** (primary goal — guarantees a live, demonstrable deployment). In parallel, provision AWS infrastructure using Terraform (ECS Fargate, RDS, ElastiCache, S3, ECR, ALB) as a stretch goal, progressing as time allows.

**Deliverable:** Application live and accessible on a real domain via Nginx reverse proxy with automated CI/CD. AWS infrastructure provisioned where time permits.

---

### Week 13 — Testing, Documentation
Write unit and integration tests targeting 80% code coverage. Complete API documentation,
architecture diagrams, and a comprehensive README. Prepare a live demo presentation of the project.

**Deliverable:** Ready project with tests, documentation, live deployment, and demo materials.

---

## Weekly Summary

| Week | Focus Area | Key Deliverable |
|------|-----------|-----------------|
| 1 | Project Foundation | Infrastructure + database schema |
| 2 | Authentication | Secure login/register/JWT system |
| 3 | Core Data API | Organizations, workspaces, competitors |
| 4 | Monitoring System | URL tracking + scrape job management |
| 5 | Scraping Pipeline | Automated change detection |
| 6 | AI Embeddings | Vector database population |
| 7 | RAG & AI Reports | Semantic search + report generation |
| 8 | Frontend Auth | Login/register UI + routing |
| 9 | Frontend Core | Dashboard + competitor management |
| 10 | Frontend AI | Search + report UI |
| 11 | Billing | Payment integration + plan limits |
| 12 | Cloud Deployment | VPS deploy with Nginx + SSL, AWS production + CI/CD |
| 13 | Testing & Docs | 80% test coverage |
