# Shiori — AI Project Lifecycle Platform

Upload project briefs. Clarify requirements. Approve plans. Execute, QA, release, and hand off — with citations grounded in your source documents.

Shiori is a full-stack Retrieval-Augmented Generation (RAG) platform for freelancers and indie builders. Work stays **project-scoped**: documents, requirements, execution, delivery, and chat belong to a single engagement.

Core loop:

`Brief → clarified scope → approved plan → daily execution → QA → release → handoff`

The AI can propose work breakdowns, check-ins, and replan diffs, but never mutates project records without explicit approval.

---

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│   FastAPI    │────▶│  PostgreSQL  │
│  TanStack    │     │   REST API   │     │  + pgvector  │
│  Start       │◀────│              │◀────│              │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                     ┌──────▼───────┐     ┌──────────────┐
                     │    Redis     │────▶│    Celery     │
                     │   (Broker)   │◀────│   Worker      │
                     └──────────────┘     └──────┬───────┘
                                                 │
                                          ┌──────▼───────┐
                                          │  sentence-   │
                                          │  transformers│
                                          └──────────────┘
```

**Two core flows:**

**Upload flow:** Client → FastAPI → saves file → Celery parses/chunks/embeds → pgvector

**Agent chat flow:** Client → project-scoped agent → tool calling (search, hybrid, page read) → Gemini answer with document citations. Optional MCP web research is **off by default**.

---

## Tech Stack

| Layer              | Technology                                                 |
| ------------------ | ---------------------------------------------------------- |
| **Backend**        | Python, FastAPI, SQLAlchemy (async), Alembic               |
| **Database**       | PostgreSQL with pgvector extension                         |
| **Vector Search**  | pgvector cosine distance (`<=>` operator)                  |
| **Embeddings**     | sentence-transformers (`all-MiniLM-L6-v2`, 384 dimensions) |
| **LLM**            | Google Gemini via LangChain LCEL                           |
| **Task Queue**     | Celery + Redis                                             |
| **Auth**           | JWT tokens with bcrypt password hashing                    |
| **Frontend**       | TanStack Start (`RAG_Frontend/citadel`), Tailwind, Axios   |
| **Infrastructure** | Docker Compose                                             |

---

## Product surfaces (API)

| Area | Prefix / routes |
|------|-----------------|
| Projects + documents | `/projects/{id}`, `/projects/{id}/documents…` |
| Requirements | `/projects/{id}/requirements` |
| Technology stack | `/projects/{id}/technology` |
| Execution | `/projects/{id}/execution`, tasks, milestones, proposals, check-in |
| Delivery | `/projects/{id}/delivery`, qa-runs, releases, handoffs |
| Project chat | `/documents/agent/query` with `project_id` |

Removed / demoted:

- Legacy simple Q&A (`POST /documents/query`)
- Global cross-document chat (unscoped agent conversations)
- Baseline / change-request / exploration workflows (dropped in earlier migrations)

---

## Quick start

```bash
cp .env.example .env   # set GOOGLE_API_KEY, JWT_SECRET
docker-compose up --build
docker-compose exec api alembic upgrade head
```

API: http://localhost:8000  
Frontend: see `../RAG_Frontend/citadel` — set `VITE_API_URL=http://localhost:8000`

Upload documents from a **project** workspace (`/projects/{id}/upload`), not a global upload page.

---

## Key design notes

- Custom chunking with page metadata for PDF citations
- pgvector in Postgres instead of a separate vector DB
- Celery for async ingest
- Approval-gated AI proposals for plans and replans
- MCP web research only when `MCP_WEB_ENABLED=true`

See also [`DEPLOY.md`](DEPLOY.md) for Fly/Vercel and optional MCP setup.

## Agency demo (MVP A)

Discovery-first flow: find leads → export CSV → convert to engagement → SOW → delivery.

See [`docs/demo/agency-first-user.md`](docs/demo/agency-first-user.md) for a 10-minute walkthrough.
