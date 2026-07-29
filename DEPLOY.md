# Deployment guide

## Fly.io (API + Celery)

1. Install [flyctl](https://fly.io/docs/hands-on/install-flyctl/)
2. From `Document_Q&A_RAG_Platform/`:
   ```bash
   fly apps create docqa-api
   fly postgres create   # or attach Neon/Supabase URL
   fly redis create      # or Upstash URL
   fly secrets set \
     DATABASE_URL="postgresql+asyncpg://..." \
     REDIS_URL="redis://..." \
     GOOGLE_API_KEY="..." \
     JWT_SECRET="..." \
     CORS_ORIGINS="https://your-app.vercel.app" \
     FRONTEND_URL="https://your-app.vercel.app" \
     SENTRY_ENVIRONMENT="production"
   fly deploy
   ```
3. Run migrations: `fly ssh console -C "alembic upgrade head"`
4. Deploy Celery worker (separate Fly app or process) with same secrets.

## Vercel (frontend)

1. Import `RAG_Frontend/citadel` repository
2. Environment: `VITE_API_URL=https://docqa-api.fly.dev`
3. Build command: `npm run build`

## Stripe (optional)

1. Create a Pro price in Stripe Dashboard
2. Set `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID_PRO`, `STRIPE_WEBHOOK_SECRET`
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

### Manual smoke test checklist

1. Set `MCP_WEB_ENABLED=true` and ensure Node/npm are available in the API container.
2. In a **project** chat, ask something that needs the open web (not covered by uploads).
3. Confirm agent trace shows a `web_research` step.
4. Confirm answer cites `[W1]` and sources panel shows **Internet · Wikipedia** with an external link.
5. Ask a document-specific question and confirm answers still cite `[D1]` from uploads when docs have the answer.
