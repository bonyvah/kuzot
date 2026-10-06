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

AI & Search: LangChain, Pinecone (Vector Database), OpenAI APIs.

Data Storage: PostgreSQL (App data), MongoDB (unstructured HTML scrapes).

Caching & Message Broker: Redis (Caching), Celery (Distributed Task Queue), RabbitMQ(Task Broker).

Web Scraping: Playwright, Rotating Proxies, Headless Browser Automation.

Auth & Security: Clerk, OAuth2, JWT Authentication, AWS Secrets Manager.

DevOps & Cloud: Docker (Containerization), Nginx (Reverse Proxy & Static Asset Serving), GitHub Actions (CI/CD), Terraform (IaC), AWS (ECS Fargate, ALB, ECR, S3, RDS, ElastiCache).