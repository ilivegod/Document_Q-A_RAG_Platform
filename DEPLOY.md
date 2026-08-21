# Deployment guide

MVP A requires **API + Celery worker + Postgres + Redis + R2**. Lead discovery will not run without the Celery app.

## Prerequisites

- [flyctl](https://fly.io/docs/hands-on/install-flyctl/) installed and logged in
- Vercel account for frontend
- Google Cloud: Gemini API key (`AIza…`) + Places API key
- Cloudflare R2 bucket for document uploads
- Resend API key for auth / closed-beta approval emails

## 1. Fly.io — API (`docqa-api`)

From `Document_Q&A_RAG_Platform/`:

```bash
fly apps create docqa-api   # once
fly postgres create         # or use Neon/Supabase DATABASE_URL
fly redis create            # or use Upstash REDIS_URL
```

Set secrets (adjust URLs for your infra):

```bash
fly secrets set \
  DATABASE_URL="postgresql+asyncpg://USER:PASS@HOST:5432/DB" \
  REDIS_URL="redis://..." \
  GOOGLE_API_KEY="AIza..." \
  GOOGLE_PLACES_API_KEY="AIza..." \
  JWT_SECRET="..." \
  JWT_ALGORITHM="HS256" \
  JWT_EXPIRATION_MINUTES="30" \
  RESEND_API_KEY="re_..." \
  EMAIL_FROM="noreply@yourdomain.com" \
  FRONTEND_URL="https://your-app.vercel.app" \
  CORS_ORIGINS="https://your-app.vercel.app" \
  API_PUBLIC_URL="https://docqa-api.fly.dev" \
  CLOSED_BETA_ENABLED="true" \
  ADMIN_EMAIL="you@example.com" \
  R2_BUCKET_NAME="..." \
  R2_ENDPOINT_URL="https://....r2.cloudflarestorage.com" \
  R2_ACCESS_KEY_ID="..." \
  R2_SECRET_ACCESS_KEY="..." \
  SENTRY_DSN="" \
  SENTRY_ENVIRONMENT="production" \
  SENTRY_TRACES_SAMPLE_RATE="0.2" \
  -a docqa-api
```

Deploy and migrate:

```bash
fly deploy -a docqa-api
fly ssh console -a docqa-api -C "alembic upgrade head"
```

Health check: `curl https://docqa-api.fly.dev/health/live`

## 2. Fly.io — Celery worker (`docqa-celery`)

```bash
fly apps create docqa-celery   # once
```

Copy the same secrets as the API (worker does not need `CORS_ORIGINS` or `FRONTEND_URL`, but sharing all secrets is fine):

```bash
# Example: copy from API app (fly secrets are per-app — set manually or script)
fly secrets set DATABASE_URL="..." REDIS_URL="..." GOOGLE_API_KEY="..." \
  GOOGLE_PLACES_API_KEY="..." JWT_SECRET="..." RESEND_API_KEY="..." \
  R2_BUCKET_NAME="..." R2_ENDPOINT_URL="..." R2_ACCESS_KEY_ID="..." \
  R2_SECRET_ACCESS_KEY="..." SENTRY_ENVIRONMENT="production" \
  -a docqa-celery
```

Deploy worker:

```bash
fly deploy -c fly.worker.toml -a docqa-celery
```

Verify: `fly logs -a docqa-celery` should show `celery@... ready.`

## 3. Vercel (frontend)

1. Import `RAG_Frontend/citadel` repository
2. Environment variables:
   - `VITE_API_URL=https://docqa-api.fly.dev` (your Fly API hostname)
   - `VITE_SENTRY_DSN=` (optional; empty disables Sentry in browser)
3. Build command: `npm run build`

## 4. Post-deploy smoke test (MVP A)

Run [`docs/demo/agency-first-user.md`](docs/demo/agency-first-user.md) against production:

- [ ] Register → admin approval email link works (`API_PUBLIC_URL` must match Fly API URL)
- [ ] Lead search completes (Celery + Places key)
- [ ] CSV export downloads
- [ ] Start engagement → upload brief → SOW generates → portal link opens

## Stripe (optional)

1. Create a Pro price in Stripe Dashboard
2. Set `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID_PRO`, `STRIPE_WEBHOOK_SECRET` on `docqa-api`
3. Webhook URL: `https://docqa-api.fly.dev/billing/webhook` — event: `checkout.session.completed`

## MCP web research (optional)

The document agent can delegate to a **web-research sub-agent** via stdio MCP servers (DuckDuckGo + Wikipedia). The API container needs:

- **Python:** `duckduckgo-mcp-server` (installed via `requirements.txt`)
- **Node.js + npm:** for `npx -y wiki-mcp` (Wikipedia MCP)

### Environment variables

```env
MCP_WEB_ENABLED=false
MCP_DDG_COMMAND=python
MCP_DDG_ARGS=-m,duckduckgo_mcp.server
MCP_WIKI_COMMAND=npx
MCP_WIKI_ARGS=-y,wiki-mcp
MCP_TOOL_TIMEOUT_SECONDS=45
WEB_RESEARCH_MAX_RESULTS=5
```

Web research is **off by default**. Set `MCP_WEB_ENABLED=true` only when you explicitly want the agent to use Wikipedia/DuckDuckGo as a supplement to project documents.

### Rate limits

Web research is capped at **10 calls per user per day** (Redis-backed).
