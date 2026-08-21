# Agency first-user demo (10 minutes)

Use this script to validate lead discovery, AI proposal research, and the core agency OS in one session.

## Prerequisites

- Backend API and Celery worker running (`docker compose up`)
- Run migrations: `alembic upgrade head` (includes `sales_proposals` table)
- `GOOGLE_PLACES_API_KEY` (or `GOOGLE_API_KEY` with Places API enabled)
- `GOOGLE_API_KEY` — Gemini key (`AIza…`) for proposals, SOW, requirements, and optional AI lead scoring
- `MCP_WEB_ENABLED=true` — enables DuckDuckGo/Wikipedia research for proposal briefs
- `RESEND_API_KEY` — only for closed-beta signup approval emails (not outreach)
- Logged-in agency user

## 1. Discover leads (~4 min)

1. Open **Leads** (`/agency/leads`)
2. Search: location `Austin, TX`, industry `dental clinic`, radius `10 km`
3. Enable **Poor website only** (optional: **No website only**)
4. Click **Find leads** and watch the progress log until complete (choose 15–50 leads per search)
5. Review the table: fit score, website badge, contact email
6. Click **Export CSV** to download leads for your own outreach (email, CRM, etc.)

## 2. Qualify a lead (~2 min)

1. Open a high-fit prospect from the table
2. Review website audit signals and heuristic fit score
3. Optional: click **Enhance with AI** for a richer summary and pitch angle
4. Confirm or edit **Contact email** and click **Save**

## 3. Research + draft proposal (~5 min)

1. On the lead detail page, click **Start research & proposal** (converts to a project if needed)
2. You land on **Project chat** with research running — watch the progress log
3. When research completes, review the **Proposal approach** card:
   - AI suggests a proposal type (e.g. website redesign) with company observations
   - Click **Confirm & draft proposal** (or **Change approach** to pick another type)
4. Review the **Draft proposal** card:
   - Read the markdown preview
   - Click **Suggest improvements** with feedback (e.g. shorter timeline) → wait for revised draft
   - Click **Approve & save**
5. Open **Documents** — you should see:
   - `{Client} - Company Brief.md` (seeded on convert)
   - `{Client} - Proposal v1.md` (after approve)
6. Wait until both documents show status **Ready** (embedding complete)
7. In **Project chat**, ask: *“What did we propose for timeline and deliverables?”* — answer should cite the proposal document

## 4. Full engagement pipeline (~optional)

1. Upload additional client briefs on **Documents** if needed
2. Open **SOW** → generate tiers → copy **portal link**
3. Skim **Requirements** and **Execution** to confirm the pipeline continues

## Success criteria

- [ ] At least one prospect search completed (Celery worker running)
- [ ] CSV export downloads with lead data
- [ ] One prospect converted to a project in `lead` pipeline stage with **Company Brief** in Documents
- [ ] Proposal research → confirm → draft → revise → approve completes end-to-end
- [ ] Approved proposal appears in Documents and is answerable via project chat RAG
- [ ] SOW generation runs on uploaded brief (optional follow-on)
- [ ] Client portal link opens and shows tiers (optional follow-on)

## Notes

- Business emails are often missing from Places — scrape + manual edit is expected
- Outreach is **manual** in MVP A: export CSV and contact leads in your own email tool
- Approved proposals are **not** auto-emailed — download from Documents and send manually
- In-app outreach (Resend drafts) is deferred — backend routes remain for a future release
- Defer for later: Gmail sync, PageSpeed API, automated follow-up sequences, app-wide chat approve actions
