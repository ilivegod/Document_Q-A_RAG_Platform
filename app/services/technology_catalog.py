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
    *keywords: str,
) -> TechnologyCatalogItem:
    return TechnologyCatalogItem(
        id=id,
        name=name,
        category=category,
        docs_url=docs_url,
        icon_slug=icon_slug,
        keywords=keywords,
    )


TECHNOLOGY_CATALOG: tuple[TechnologyCatalogItem, ...] = (
    _item(
        "nextjs",
        "Next.js",
        TechnologyCategory.FRONTEND,
        "https://nextjs.org/docs",
        "nextdotjs",
        "react",
        "ssr",
        "frontend",
    ),
    _item(
        "react",
        "React",
        TechnologyCategory.FRONTEND,
        "https://react.dev",
        "react",
        "frontend",
        "spa",
    ),
    _item(
        "vue",
        "Vue.js",
        TechnologyCategory.FRONTEND,
        "https://vuejs.org/guide/introduction.html",
        "vuedotjs",
        "frontend",
        "spa",
    ),
    _item(
        "angular",
        "Angular",
        TechnologyCategory.FRONTEND,
        "https://angular.dev/overview",
        "angular",
        "frontend",
        "spa",
    ),
    _item(
        "sveltekit",
        "SvelteKit",
        TechnologyCategory.FRONTEND,
        "https://svelte.dev/docs/kit/introduction",
        "svelte",
        "frontend",
        "ssr",
    ),
    _item(
        "tailwindcss",
        "Tailwind CSS",
        TechnologyCategory.FRONTEND,
        "https://tailwindcss.com/docs",
        "tailwindcss",
        "css",
        "styling",
    ),
    _item(
        "shadcn",
        "shadcn/ui",
        TechnologyCategory.FRONTEND,
        "https://ui.shadcn.com/docs",
        "shadcnui",
        "components",
        "react",
    ),
    _item(
        "fastapi",
        "FastAPI",
        TechnologyCategory.BACKEND,
        "https://fastapi.tiangolo.com",
        "fastapi",
        "python",
        "api",
        "backend",
    ),
    _item(
        "django",
        "Django",
        TechnologyCategory.BACKEND,
        "https://docs.djangoproject.com",
        "django",
        "python",
        "backend",
    ),
    _item(
        "express",
        "Express",
        TechnologyCategory.BACKEND,
        "https://expressjs.com",
        "express",
        "node",
        "javascript",
        "backend",
    ),
    _item(
        "nestjs",
        "NestJS",
        TechnologyCategory.BACKEND,
        "https://docs.nestjs.com",
        "nestjs",
        "node",
        "typescript",
        "backend",
    ),
    _item(
        "nodejs",
        "Node.js",
        TechnologyCategory.BACKEND,
        "https://nodejs.org/docs/latest/api/",
        "nodedotjs",
        "javascript",
        "runtime",
    ),
    _item(
        "python",
        "Python",
        TechnologyCategory.BACKEND,
        "https://docs.python.org/3/",
        "python",
        "language",
    ),
    _item(
        "postgresql",
        "PostgreSQL",
        TechnologyCategory.DATABASE,
        "https://www.postgresql.org/docs/",
        "postgresql",
        "sql",
        "database",
        "postgres",
    ),
    _item(
        "mysql",
        "MySQL",
        TechnologyCategory.DATABASE,
        "https://dev.mysql.com/doc/",
        "mysql",
        "sql",
        "database",
    ),
    _item(
        "mongodb",
        "MongoDB",
        TechnologyCategory.DATABASE,
        "https://www.mongodb.com/docs/",
        "mongodb",
        "nosql",
        "database",
    ),
    _item(
        "redis",
        "Redis",
        TechnologyCategory.DATABASE,
        "https://redis.io/docs/latest/",
        "redis",
        "cache",
        "database",
    ),
    _item(
        "supabase",
        "Supabase",
        TechnologyCategory.DATABASE,
        "https://supabase.com/docs",
        "supabase",
        "postgres",
        "backend",
        "baas",
    ),
    _item(
        "pgvector",
        "pgvector",
        TechnologyCategory.DATABASE,
        "https://github.com/pgvector/pgvector",
        "postgresql",
        "vector",
        "embeddings",
        "ai",
    ),
    _item(
        "openai",
        "OpenAI",
        TechnologyCategory.AI,
        "https://platform.openai.com/docs",
        "openai",
        "llm",
        "ai",
        "gpt",
    ),
    _item(
        "gemini",
        "Google Gemini",
        TechnologyCategory.AI,
        "https://ai.google.dev/gemini-api/docs",
        "googlegemini",
        "llm",
        "ai",
        "google",
    ),
    _item(
        "anthropic",
        "Anthropic",
        TechnologyCategory.AI,
        "https://docs.anthropic.com",
        "anthropic",
        "llm",
        "ai",
        "claude",
    ),
    _item(
        "langchain",
        "LangChain",
        TechnologyCategory.AI,
        "https://python.langchain.com/docs/",
        "langchain",
        "llm",
        "ai",
        "agents",
    ),
    _item(
        "clerk",
        "Clerk",
        TechnologyCategory.AUTHENTICATION,
        "https://clerk.com/docs",
        "clerk",
        "auth",
        "authentication",
    ),
    _item(
        "auth0",
        "Auth0",
        TechnologyCategory.AUTHENTICATION,
        "https://auth0.com/docs",
        "auth0",
        "auth",
        "authentication",
    ),
    _item(
        "firebase-auth",
        "Firebase Auth",
        TechnologyCategory.AUTHENTICATION,
        "https://firebase.google.com/docs/auth",
        "firebase",
        "auth",
        "google",
    ),
    _item(
        "nextauth",
        "NextAuth.js",
        TechnologyCategory.AUTHENTICATION,
        "https://authjs.dev",
        "authjs",
        "auth",
        "nextjs",
    ),
    _item(
        "vercel",
        "Vercel",
        TechnologyCategory.HOSTING,
        "https://vercel.com/docs",
        "vercel",
        "hosting",
        "deployment",
        "nextjs",
    ),
    _item(
        "netlify",
        "Netlify",
        TechnologyCategory.HOSTING,
        "https://docs.netlify.com",
        "netlify",
        "hosting",
        "deployment",
    ),
    _item(
        "railway",
        "Railway",
        TechnologyCategory.HOSTING,
        "https://docs.railway.com",
        "railway",
        "hosting",
        "deployment",
        "paas",
    ),
    _item(
        "flyio",
        "Fly.io",
        TechnologyCategory.HOSTING,
        "https://fly.io/docs/",
        "flydotio",
        "hosting",
        "deployment",
    ),
    _item(
        "aws",
        "AWS",
        TechnologyCategory.HOSTING,
        "https://docs.aws.amazon.com",
        "amazonwebservices",
        "cloud",
        "hosting",
        "infrastructure",
    ),
    _item(
        "cloudflare",
        "Cloudflare",
        TechnologyCategory.HOSTING,
        "https://developers.cloudflare.com",
        "cloudflare",
        "cdn",
        "workers",
        "hosting",
    ),
    _item(
        "s3",
        "Amazon S3",
        TechnologyCategory.STORAGE,
        "https://docs.aws.amazon.com/AmazonS3/latest/userguide/",
        "amazons3",
        "storage",
        "files",
        "aws",
    ),
    _item(
        "cloudinary",
        "Cloudinary",
        TechnologyCategory.STORAGE,
        "https://cloudinary.com/documentation",
        "cloudinary",
        "images",
        "storage",
        "media",
    ),
    _item(
        "vitest",
        "Vitest",
        TechnologyCategory.TESTING,
        "https://vitest.dev/guide/",
        "vitest",
        "testing",
        "unit",
        "javascript",
    ),
    _item(
        "playwright",
        "Playwright",
        TechnologyCategory.TESTING,
        "https://playwright.dev/docs/intro",
        "playwright",
        "testing",
        "e2e",
    ),
    _item(
        "pytest",
        "pytest",
        TechnologyCategory.TESTING,
        "https://docs.pytest.org",
        "pytest",
        "testing",
        "python",
    ),
    _item(
        "stripe",
        "Stripe",
        TechnologyCategory.PAYMENTS,
        "https://docs.stripe.com",
        "stripe",
        "payments",
        "billing",
    ),
    _item(
        "docker",
        "Docker",
        TechnologyCategory.DEVOPS,
        "https://docs.docker.com",
        "docker",
        "containers",
        "devops",
    ),
    _item(
        "github-actions",
        "GitHub Actions",
        TechnologyCategory.DEVOPS,
        "https://docs.github.com/en/actions",
        "githubactions",
        "ci",
        "cd",
        "devops",
    ),
    _item(
        "terraform",
        "Terraform",
        TechnologyCategory.DEVOPS,
        "https://developer.hashicorp.com/terraform/docs",
        "terraform",
        "iac",
        "devops",
        "infrastructure",
    ),
    _item(
        "celery",
        "Celery",
        TechnologyCategory.OTHER,
        "https://docs.celeryq.dev",
        "celery",
        "tasks",
        "queue",
        "python",
    ),
    _item(
        "rabbitmq",
        "RabbitMQ",
        TechnologyCategory.OTHER,
        "https://www.rabbitmq.com/docs",
        "rabbitmq",
        "queue",
        "messaging",
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
