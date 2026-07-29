# Shiori — AI-Powered Project Document Intelligence

Upload project documents. Ask questions. Capture requirements, analyze changes, and log decisions — all with citations.

Shiori is a full-stack Retrieval-Augmented Generation (RAG) platform for freelancers and indie builders. Organize work in project workspaces, upload PDFs and DOCX files, then use agentic workflows to understand scope, shape your technology stack, and chat with citations grounded in your source material.

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

**Upload flow:** Client → FastAPI → saves file → dispatches Celery task → Worker parses document → chunks text with overlap → generates embeddings via sentence-transformers → stores vectors in pgvector

**Query flow:** Client → FastAPI → embeds question → cosine similarity search in pgvector → retrieves top-k chunks → LangChain composes prompt with context → Gemini generates answer → response with citations

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
| **Frontend**       | TanStack Start, Tailwind CSS, Axios                        |
| **Infrastructure** | Docker Compose                                             |

---

## Key Design Decisions

### Custom chunking over LangChain splitters

I built the text chunking logic from scratch rather than using LangChain's `RecursiveCharacterTextSplitter`. The chunker uses a sliding window with configurable size and overlap, detects word boundaries to avoid mid-word splits, and preserves page-level metadata for citations. This gives full control over chunking behavior and demonstrates understanding of how chunking affects retrieval quality.

### pgvector over standalone vector databases

Instead of Pinecone or Weaviate, I use PostgreSQL's pgvector extension. This keeps the entire data layer in one database — chunks, metadata, embeddings, and user data all live together. Queries can join across tables (e.g., filtering chunks by document owner) without cross-service calls. For the scale of this project, a single Postgres instance outperforms the operational complexity of a separate vector DB.

### LangChain for orchestration, custom code for core logic

LangChain handles the LLM chain composition (prompt → model → output parser via LCEL), while embedding generation, vector search, and chunking are all custom. This avoids over-abstracting the parts that matter most for retrieval quality while using LangChain where it adds genuine value.

### Async pipeline with Celery

Document processing (parse → chunk → embed → store) runs as a Celery task dispatched to Redis. This prevents long uploads from blocking the API, allows status tracking, and makes the processing pipeline independently scalable. Each task creates its own database engine to avoid event loop conflicts between FastAPI and Celery processes.

### Raw SQL for vector search

The similarity search query is written as raw SQL against pgvector rather than through an ORM abstraction. This makes the cosine distance operator (`<=>`), JOIN logic, and filtering explicit and debuggable.

---

## Project Structure

```
doc-qa-platform/
├── app/
│   ├── main.py                 # FastAPI app + CORS + middleware
│   ├── config.py               # Pydantic settings from .env
│   ├── database.py             # Async SQLAlchemy engine + session
│   ├── models/
│   │   ├── user.py             # User model (UUID, bcrypt hash)
│   │   ├── document.py         # Document model (status enum)
│   │   └── chunk.py            # Chunk model (vector(384) column)
│   ├── schemas/
│   │   └── auth.py             # Pydantic schemas for auth
│   ├── routers/
│   │   ├── auth.py             # Register + login endpoints
│   │   ├── documents.py        # Upload, list, delete endpoints
│   │   └── query.py            # Q&A endpoint
│   ├── services/
│   │   ├── parsing.py          # PDF/DOCX text extraction
│   │   ├── chunking.py         # Custom sliding window chunker
│   │   ├── embedding.py        # Batch embedding with sentence-transformers
│   │   ├── retrieval.py        # pgvector similarity search (raw SQL)
│   │   ├── qa_chain.py         # LangChain LCEL chain (Gemini)
│   │   └── pipeline.py         # End-to-end processing orchestrator
│   ├── workers/
│   │   ├── celery_app.py       # Celery configuration
│   │   └── tasks.py            # Async document processing task
│   ├── middleware/
│   │   └── error_handler.py    # Global error handling
│   └── dependencies/
│       └── getUser.py          # Auth dependencies (JWT decode)
├── client/                     # TanStack Start frontend
│   └── src/
│       ├── routes/             # File-based routing
│       ├── components/         # Navbar, ChatWindow, FileUpload, etc.
│       └── utils/              # API client (Axios), auth helpers
├── alembic/                    # Database migrations
├── docker-compose.yml          # Full stack orchestration
├── Dockerfile                  # Python 3.12 + CPU-only PyTorch
└── requirements.txt
```

---

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for frontend)
- A Google AI Studio API key ([get one free](https://aistudio.google.com/apikey))

### 1. Clone and configure

```bash
git clone https://github.com/ilivegod/docqa.git
cd docqa
```

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql+asyncpg://docqa:docqa123@postgres:5432/docqa_db
REDIS_URL=redis://redis:6379/0
GOOGLE_API_KEY=your_google_api_key_here
JWT_SECRET=your_random_secret_string_here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=30
```

### 2. Start the backend

```bash
docker-compose up --build
```

This starts PostgreSQL (with pgvector), Redis, the FastAPI server, and the Celery worker.

### 3. Run database migrations

```bash
docker-compose exec api alembic upgrade head
```

Only needed on first run or after schema changes.

### 4. Start the frontend

```bash
cd client
npm install
npm run dev
```

The app is now running at `http://localhost:3000`.

---

## Usage

1. **Register** an account at `/register`
2. **Upload** a PDF or DOCX document at `/upload`
3. Wait for processing (status changes from "Uploaded" → "Processing" → "Ready")
4. **Ask questions** about your document in the chat interface
5. View **source citations** with page numbers for each answer

---

## Docker Commands Reference

```bash
# Start everything
docker-compose up --build

# Start in background
docker-compose up -d

# Run migrations
docker-compose exec api alembic upgrade head

# View logs
docker-compose logs api
docker-compose logs celery_worker

# Stop everything
docker-compose down

# Stop and delete data
docker-compose down -v
```

---

## Document agent (MCP-inspired tools)

`POST /documents/agent/query` runs a tool-using agent (Gemini + LangChain) with:

| Tool | Tier | Description |
|------|------|-------------|
| `search_documents` | Free | pgvector semantic search |
| `list_user_documents` | Free | List uploaded docs |
| `keyword_search` | Pro | Hybrid FTS + vector (`content_tsv`) |
| `get_page_content` | Pro | Full page text by page number |
| `web_research` | Pro | MCP web search (Wikipedia + DuckDuckGo) |

Set `"stream": true` for SSE (`tool_step`, `token`, `done` events). Agent traces are stored on assistant messages (`agent_trace` JSONB).

Cross-document chat: `document_id` omitted + global conversation (`document_id IS NULL`).

## Retrieval evaluation

```bash
python -m eval.run_eval --user-id <uuid> --dataset eval/dataset.json
python -m eval.run_eval --user-id <uuid> --hybrid --output eval/results_hybrid.json
```

Fill `eval/dataset.json` with questions and relevant chunk UUIDs after uploading a test PDF.

## Deployment

- API: `fly.toml` — `fly deploy` from this directory
- Set production secrets: `DATABASE_URL`, `REDIS_URL`, `GOOGLE_API_KEY`, `JWT_SECRET`, `CORS_ORIGINS`, optional Stripe keys

## What I'd Do Next

- **Multiple LLM providers** — OpenAI / Ollama via configurable provider
- **TXT and web link ingestion** — extend parsers
- **Google OAuth** — social login
- **Cross-encoder reranking** — rerank top-20 before final top-5

---
