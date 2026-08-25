# Project Overview

An AI-powered Competitive Intelligence (CI) platform designed to automate the tracking, ingestion, and analysis of competitor activities. It continuously monitors competitor digital footprints—such as pricing updates, feature launches, marketing copy, and news—and enables users to perform real-time semantic search and automated intelligence synthesis via Retrieval-Augmented Generation (RAG).

## Core Capabilities

- Automated Web Monitoring: Asynchronous scraping and change detection across competitor websites, press releases, and product documentation.
- Semantic Vector Search: Deep contextual querying across large volumes of unstructured competitor content.
- AI Analysis & Reporting: LLM-driven summarization, positioning comparisons, and trend extraction.

## Tech Stack

| Layer | Technology | Key Responsibility |
| --- | --- | --- |
| Backend Framework | Python / FastAPI | High-performance async REST API, request routing, and business logic. |
| Relational Storage | PostgreSQL | Structured relational data: user management, competitor profiles, URL registries, and audit logs. |
| Document Store | MongoDB | Raw ingestion data lake: full HTML dumps, raw API JSON responses, and versioned page snapshots. |
| Vector Database | Pinecone | Dense vector storage and similarity search for document embeddings. |
| AI Orchestration | LangChain | Text splitting, embedding generation, prompt management, and RAG retrieval pipelines. |
| Background Processing | Celery + Redis | Distributed task queue for asynchronous web scraping and background embedding jobs. |