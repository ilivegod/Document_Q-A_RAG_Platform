"""Curated technology catalog for project stack suggestions and manual add."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.project_technology import TechnologyCategory


@dataclass(frozen=True, slots=True)
class TechnologyCatalogItem:
    id: str
    name: str
    category: TechnologyCategory
    docs_url: str
    icon_slug: str
    summary: str
    usage_hint: str
    keywords: tuple[str, ...]


CATEGORY_LABELS: dict[TechnologyCategory, str] = {
    TechnologyCategory.FRONTEND: "Frontend",
    TechnologyCategory.BACKEND: "Backend",
    TechnologyCategory.DATABASE: "Database",
    TechnologyCategory.AI: "AI",
    TechnologyCategory.AUTHENTICATION: "Authentication",
    TechnologyCategory.HOSTING: "Hosting",
    TechnologyCategory.STORAGE: "Storage",
    TechnologyCategory.TESTING: "Testing",
    TechnologyCategory.PAYMENTS: "Payments",
    TechnologyCategory.DEVOPS: "DevOps",
    TechnologyCategory.OTHER: "Other",
}

CATEGORY_DESCRIPTIONS: dict[TechnologyCategory, str] = {
    TechnologyCategory.FRONTEND: (
        "User-facing UI, routing, and client-side interactions that people see and click."
    ),
    TechnologyCategory.BACKEND: (
        "Server-side APIs, business logic, and services that power your application."
    ),
    TechnologyCategory.DATABASE: (
        "Persistent data storage, queries, caching, and structured records for your app."
    ),
    TechnologyCategory.AI: (
        "LLMs, embeddings, and AI tooling for intelligent features in your product."
    ),
    TechnologyCategory.AUTHENTICATION: (
        "Sign-up, login, sessions, and identity management for your users."
    ),
    TechnologyCategory.HOSTING: (
        "Where your app runs in production — deployment, scaling, and uptime."
    ),
    TechnologyCategory.STORAGE: (
        "File, image, and media storage beyond relational database rows."
    ),
    TechnologyCategory.TESTING: (
        "Automated checks that catch regressions before you ship."
    ),
    TechnologyCategory.PAYMENTS: (
        "Billing, subscriptions, and checkout for monetizing your product."
    ),
    TechnologyCategory.DEVOPS: (
        "Containers, CI/CD, and infrastructure automation for reliable delivery."
    ),
    TechnologyCategory.OTHER: (
        "Supporting tools like queues and messaging that don't fit other categories."
    ),
}

CATEGORY_ORDER: list[TechnologyCategory] = [
    TechnologyCategory.FRONTEND,
    TechnologyCategory.BACKEND,
    TechnologyCategory.DATABASE,
    TechnologyCategory.AI,
    TechnologyCategory.AUTHENTICATION,
    TechnologyCategory.HOSTING,
    TechnologyCategory.STORAGE,
    TechnologyCategory.TESTING,
    TechnologyCategory.PAYMENTS,
    TechnologyCategory.DEVOPS,
    TechnologyCategory.OTHER,
]


def _item(
    id: str,
    name: str,
    category: TechnologyCategory,
    docs_url: str,
    icon_slug: str,
    summary: str,
    usage_hint: str,
    *keywords: str,
) -> TechnologyCatalogItem:
    return TechnologyCatalogItem(
        id=id,
        name=name,
        category=category,
        docs_url=docs_url,
        icon_slug=icon_slug,
        summary=summary,
        usage_hint=usage_hint,
        keywords=keywords,
    )


TECHNOLOGY_CATALOG: tuple[TechnologyCatalogItem, ...] = (
    _item(
        "nextjs",
        "Next.js",
        TechnologyCategory.FRONTEND,
        "https://nextjs.org/docs",
        "nextdotjs",
        "React framework with server rendering, routing, and API routes built in.",
        "Create pages under app/, fetch data in server components, deploy to Vercel.",
        "react", "ssr", "frontend",
    ),
    _item(
        "react",
        "React",
        TechnologyCategory.FRONTEND,
        "https://react.dev",
        "react",
        "Component-based JavaScript library for building interactive user interfaces.",
        "Build UI as reusable components, manage state with hooks, bundle with Vite or CRA.",
        "frontend", "spa",
    ),
    _item(
        "vue",
        "Vue.js",
        TechnologyCategory.FRONTEND,
        "https://vuejs.org/guide/introduction.html",
        "vuedotjs",
        "Progressive JavaScript framework for building reactive single-page applications.",
        "Define components with SFCs, use Vue Router for pages, add Pinia for state.",
        "frontend", "spa",
    ),
    _item(
        "angular",
        "Angular",
        TechnologyCategory.FRONTEND,
        "https://angular.dev/overview",
        "angular",
        "Full-featured TypeScript framework with batteries-included structure.",
        "Scaffold with CLI, use modules/components/services, rely on built-in routing and DI.",
        "frontend", "spa",
    ),
    _item(
        "sveltekit",
        "SvelteKit",
        TechnologyCategory.FRONTEND,
        "https://svelte.dev/docs/kit/introduction",
        "svelte",
        "Svelte-based framework with file routing and flexible SSR/SPA modes.",
        "Add routes in src/routes, use load functions for data, deploy as static or server.",
        "frontend", "ssr",
    ),
    _item(
        "tailwindcss",
        "Tailwind CSS",
        TechnologyCategory.FRONTEND,
        "https://tailwindcss.com/docs",
        "tailwindcss",
        "Utility-first CSS framework for rapid, consistent styling.",
        "Apply utility classes in JSX/HTML, extend theme in config, purge unused styles at build.",
        "css", "styling",
    ),
    _item(
        "shadcn",
        "shadcn/ui",
        TechnologyCategory.FRONTEND,
        "https://ui.shadcn.com/docs",
        "shadcnui",
        "Copy-paste React components built on Radix UI and Tailwind.",
        "Add components via CLI, customize in your codebase, compose into pages and forms.",
        "components", "react",
    ),
    _item(
        "fastapi",
        "FastAPI",
        TechnologyCategory.BACKEND,
        "https://fastapi.tiangolo.com",
        "fastapi",
        "Modern Python web framework for high-performance APIs with automatic OpenAPI docs.",
        "Define routes with type hints, validate with Pydantic, run with Uvicorn.",
        "python", "api", "backend",
    ),
    _item(
        "django",
        "Django",
        TechnologyCategory.BACKEND,
        "https://docs.djangoproject.com",
        "django",
        "Batteries-included Python web framework with ORM, admin, and auth.",
        "Create apps and models, use Django REST for APIs, migrate schema with manage.py.",
        "python", "backend",
    ),
    _item(
        "express",
        "Express",
        TechnologyCategory.BACKEND,
        "https://expressjs.com",
        "express",
        "Minimal Node.js web framework for HTTP APIs and middleware pipelines.",
        "Define routes and middleware, connect a database driver, listen on a port.",
        "node", "javascript", "backend",
    ),
    _item(
        "nestjs",
        "NestJS",
        TechnologyCategory.BACKEND,
        "https://docs.nestjs.com",
        "nestjs",
        "Structured Node.js framework inspired by Angular with dependency injection.",
        "Organize into modules/controllers/services, use decorators, integrate TypeORM or Prisma.",
        "node", "typescript", "backend",
    ),
    _item(
        "nodejs",
        "Node.js",
        TechnologyCategory.BACKEND,
        "https://nodejs.org/docs/latest/api/",
        "nodedotjs",
        "JavaScript runtime for building server-side applications and tooling.",
        "Run JS on the server, use npm packages, pair with Express or Fastify for APIs.",
        "javascript", "runtime",
    ),
    _item(
        "python",
        "Python",
        TechnologyCategory.BACKEND,
        "https://docs.python.org/3/",
        "python",
        "General-purpose language widely used for backends, scripting, and data work.",
        "Write scripts or APIs, use virtualenv/poetry, pair with FastAPI or Django.",
        "language",
    ),
    _item(
        "postgresql",
        "PostgreSQL",
        TechnologyCategory.DATABASE,
        "https://www.postgresql.org/docs/",
        "postgresql",
        "Reliable open-source relational database with strong SQL and extensions.",
        "Model tables with migrations, query via ORM or SQL, index for performance.",
        "sql", "database", "postgres",
    ),
    _item(
        "mysql",
        "MySQL",
        TechnologyCategory.DATABASE,
        "https://dev.mysql.com/doc/",
        "mysql",
        "Popular relational database for web applications and transactional data.",
        "Define schemas, run queries through your ORM, replicate for read scaling if needed.",
        "sql", "database",
    ),
    _item(
        "mongodb",
        "MongoDB",
        TechnologyCategory.DATABASE,
        "https://www.mongodb.com/docs/",
        "mongodb",
        "Document database storing flexible JSON-like records.",
        "Store collections of documents, query with drivers or Mongoose, index key fields.",
        "nosql", "database",
    ),
    _item(
        "redis",
        "Redis",
        TechnologyCategory.DATABASE,
        "https://redis.io/docs/latest/",
        "redis",
        "In-memory data store used for caching, sessions, and pub/sub.",
        "Cache hot queries, store session tokens, use as Celery broker or rate-limit backend.",
        "cache", "database",
    ),
    _item(
        "supabase",
        "Supabase",
        TechnologyCategory.DATABASE,
        "https://supabase.com/docs",
        "supabase",
        "Open-source Firebase alternative built on Postgres with auth and realtime.",
        "Use hosted Postgres, enable Row Level Security, call REST or client SDK from frontend.",
        "postgres", "backend", "baas",
    ),
    _item(
        "pgvector",
        "pgvector",
        TechnologyCategory.DATABASE,
        "https://github.com/pgvector/pgvector",
        "postgresql",
        "Postgres extension for storing and searching vector embeddings.",
        "Add vector columns, index with HNSW, run similarity search for RAG retrieval.",
        "vector", "embeddings", "ai",
    ),
    _item(
        "openai",
        "OpenAI",
        TechnologyCategory.AI,
        "https://platform.openai.com/docs",
        "openai",
        "API platform for GPT models, embeddings, and AI-powered features.",
        "Call chat/completions API, store API keys securely, stream responses to your UI.",
        "llm", "ai", "gpt",
    ),
    _item(
        "gemini",
        "Google Gemini",
        TechnologyCategory.AI,
        "https://ai.google.dev/gemini-api/docs",
        "googlegemini",
        "Google's multimodal LLM family for text, code, and structured output.",
        "Use Gemini API or LangChain adapter, set GOOGLE_API_KEY, parse structured JSON responses.",
        "llm", "ai", "google",
    ),
    _item(
        "anthropic",
        "Anthropic",
        TechnologyCategory.AI,
        "https://docs.anthropic.com",
        "anthropic",
        "Claude models for long-context reasoning and safe assistant behavior.",
        "Call Messages API with your API key, pass system prompts, handle tool use if needed.",
        "llm", "ai", "claude",
    ),
    _item(
        "langchain",
        "LangChain",
        TechnologyCategory.AI,
        "https://python.langchain.com/docs/",
        "langchain",
        "Framework for chaining LLMs, tools, retrieval, and agents.",
        "Compose prompts and tools, wire vector stores for RAG, run agent loops with tracing.",
        "llm", "ai", "agents",
    ),
    _item(
        "clerk",
        "Clerk",
        TechnologyCategory.AUTHENTICATION,
        "https://clerk.com/docs",
        "clerk",
        "Hosted authentication with prebuilt UI components and user management.",
        "Add Clerk provider to your app, use sign-in components, read session in API routes.",
        "auth", "authentication",
    ),
    _item(
        "auth0",
        "Auth0",
        TechnologyCategory.AUTHENTICATION,
        "https://auth0.com/docs",
        "auth0",
        "Identity platform supporting OAuth, SSO, and enterprise login flows.",
        "Configure application in dashboard, integrate SDK, protect routes with JWT middleware.",
        "auth", "authentication",
    ),
    _item(
        "firebase-auth",
        "Firebase Auth",
        TechnologyCategory.AUTHENTICATION,
        "https://firebase.google.com/docs/auth",
        "firebase",
        "Google-backed auth service with email, social, and phone providers.",
        "Enable providers in console, use Firebase SDK on client, verify tokens on backend.",
        "auth", "google",
    ),
    _item(
        "nextauth",
        "NextAuth.js",
        TechnologyCategory.AUTHENTICATION,
        "https://authjs.dev",
        "authjs",
        "Open-source auth library for Next.js with many OAuth providers.",
        "Configure providers in auth.ts, add session callbacks, protect pages with middleware.",
        "auth", "nextjs",
    ),
    _item(
        "vercel",
        "Vercel",
        TechnologyCategory.HOSTING,
        "https://vercel.com/docs",
        "vercel",
        "Frontend cloud platform optimized for Next.js and static sites.",
        "Connect Git repo, set env vars, deploy on push with preview URLs per branch.",
        "hosting", "deployment", "nextjs",
    ),
    _item(
        "netlify",
        "Netlify",
        TechnologyCategory.HOSTING,
        "https://docs.netlify.com",
        "netlify",
        "Jamstack hosting with CI, serverless functions, and edge delivery.",
        "Deploy from Git, add netlify.toml, use functions for lightweight backend logic.",
        "hosting", "deployment",
    ),
    _item(
        "railway",
        "Railway",
        TechnologyCategory.HOSTING,
        "https://docs.railway.com",
        "railway",
        "Simple PaaS for deploying apps, databases, and workers from Git.",
        "Create a project, connect repo, provision Postgres/Redis, deploy services with env vars.",
        "hosting", "deployment", "paas",
    ),
    _item(
        "flyio",
        "Fly.io",
        TechnologyCategory.HOSTING,
        "https://fly.io/docs/",
        "flydotio",
        "Global app platform running containers close to users.",
        "Ship a Dockerfile, use fly.toml, scale machines per region as traffic grows.",
        "hosting", "deployment",
    ),
    _item(
        "aws",
        "AWS",
        TechnologyCategory.HOSTING,
        "https://docs.aws.amazon.com",
        "amazonwebservices",
        "Comprehensive cloud platform for compute, storage, and managed services.",
        "Pick services (EC2, ECS, Lambda), use IAM for access, automate with CloudFormation.",
        "cloud", "hosting", "infrastructure",
    ),
    _item(
        "cloudflare",
        "Cloudflare",
        TechnologyCategory.HOSTING,
        "https://developers.cloudflare.com",
        "cloudflare",
        "CDN, DNS, Workers, and edge compute for fast global delivery.",
        "Point DNS to Cloudflare, cache static assets, run Workers at the edge for APIs.",
        "cdn", "workers", "hosting",
    ),
    _item(
        "s3",
        "Amazon S3",
        TechnologyCategory.STORAGE,
        "https://docs.aws.amazon.com/AmazonS3/latest/userguide/",
        "amazons3",
        "Object storage for files, backups, and static assets at scale.",
        "Create buckets, upload via SDK or presigned URLs, set lifecycle and access policies.",
        "storage", "files", "aws",
    ),
    _item(
        "cloudinary",
        "Cloudinary",
        TechnologyCategory.STORAGE,
        "https://cloudinary.com/documentation",
        "cloudinary",
        "Media management with uploads, transforms, and CDN delivery.",
        "Upload images/videos via widget or API, apply transforms in URLs, serve optimized assets.",
        "images", "storage", "media",
    ),
    _item(
        "vitest",
        "Vitest",
        TechnologyCategory.TESTING,
        "https://vitest.dev/guide/",
        "vitest",
        "Fast unit test runner built for Vite and modern JavaScript projects.",
        "Write tests alongside source, mock modules, run in watch mode during development.",
        "testing", "unit", "javascript",
    ),
    _item(
        "playwright",
        "Playwright",
        TechnologyCategory.TESTING,
        "https://playwright.dev/docs/intro",
        "playwright",
        "End-to-end browser testing across Chromium, Firefox, and WebKit.",
        "Write user-flow tests, run headless in CI, capture traces on failure.",
        "testing", "e2e",
    ),
    _item(
        "pytest",
        "pytest",
        TechnologyCategory.TESTING,
        "https://docs.pytest.org",
        "pytest",
        "Python testing framework with fixtures and expressive assertions.",
        "Write test functions, use fixtures for DB/API setup, run with pytest -q in CI.",
        "testing", "python",
    ),
    _item(
        "stripe",
        "Stripe",
        TechnologyCategory.PAYMENTS,
        "https://docs.stripe.com",
        "stripe",
        "Payments platform for checkout, subscriptions, and invoicing.",
        "Create products/prices in dashboard, integrate Checkout or Elements, handle webhooks.",
        "payments", "billing",
    ),
    _item(
        "docker",
        "Docker",
        TechnologyCategory.DEVOPS,
        "https://docs.docker.com",
        "docker",
        "Container platform for packaging apps with reproducible environments.",
        "Write a Dockerfile, build images, run containers locally and in production orchestrators.",
        "containers", "devops",
    ),
    _item(
        "github-actions",
        "GitHub Actions",
        TechnologyCategory.DEVOPS,
        "https://docs.github.com/en/actions",
        "githubactions",
        "CI/CD workflows triggered by Git events in your repository.",
        "Add workflow YAML, run tests on PR, deploy on merge to main with secrets.",
        "ci", "cd", "devops",
    ),
    _item(
        "terraform",
        "Terraform",
        TechnologyCategory.DEVOPS,
        "https://developer.hashicorp.com/terraform/docs",
        "terraform",
        "Infrastructure-as-code tool for provisioning cloud resources declaratively.",
        "Define .tf files, plan changes, apply to create/update cloud infrastructure safely.",
        "iac", "devops", "infrastructure",
    ),
    _item(
        "celery",
        "Celery",
        TechnologyCategory.OTHER,
        "https://docs.celeryq.dev",
        "celery",
        "Distributed task queue for running background jobs in Python.",
        "Define tasks, configure a broker (Redis/RabbitMQ), run workers to process async jobs.",
        "tasks", "queue", "python",
    ),
    _item(
        "rabbitmq",
        "RabbitMQ",
        TechnologyCategory.OTHER,
        "https://www.rabbitmq.com/docs",
        "rabbitmq",
        "Message broker for reliable async communication between services.",
        "Declare queues/exchanges, publish messages from producers, consume in worker processes.",
        "queue", "messaging",
    ),
)

_CATALOG_BY_ID: dict[str, TechnologyCatalogItem] = {
    item.id: item for item in TECHNOLOGY_CATALOG
}


def get_catalog_item(catalog_id: str) -> TechnologyCatalogItem | None:
    return _CATALOG_BY_ID.get(catalog_id)


def search_catalog(query: str, limit: int = 12) -> list[TechnologyCatalogItem]:
    q = query.strip().lower()
    if not q:
        return list(TECHNOLOGY_CATALOG[:limit])

    scored: list[tuple[int, TechnologyCatalogItem]] = []
    for item in TECHNOLOGY_CATALOG:
        haystack = " ".join(
            [item.id, item.name.lower(), item.category.value, *item.keywords]
        )
        if q in item.name.lower() or q in item.id:
            scored.append((0, item))
        elif q in haystack:
            scored.append((1, item))
        elif any(q in kw for kw in item.keywords):
            scored.append((2, item))

    scored.sort(key=lambda pair: (pair[0], pair[1].name.lower()))
    return [item for _, item in scored[:limit]]


def catalog_ids_by_category() -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for item in TECHNOLOGY_CATALOG:
        grouped.setdefault(item.category.value, []).append(item.id)
    return grouped
