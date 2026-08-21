# Agency first-user demo (10 minutes)

Use this script to validate lead discovery and the core agency OS in one session.

## Prerequisites

- Backend API and Celery worker running (`docker compose up`)
- `GOOGLE_PLACES_API_KEY` (or `GOOGLE_API_KEY` with Places API enabled)
- `GOOGLE_API_KEY` — Gemini key (`AIza…`) for SOW, requirements, and optional AI lead scoring
- `RESEND_API_KEY` — only for closed-beta signup approval emails (not outreach)
- Logged-in agency user

## 1. Discover leads (~4 min)

1. Open **Leads** (`/agency/leads`)
2. Search: location `Austin, TX`, industry `dental clinic`, radius `10 km`
3. Enable **Poor website only** (optional: **No website only**)
4. Click **Find leads** and watch the progress log until complete (up to 15 leads)
5. Review the table: fit score, website badge, contact email
6. Click **Export CSV** to download leads for your own outreach (email, CRM, etc.)

## 2. Qualify a lead (~2 min)

1. Open a high-fit prospect from the table
2. Review website audit signals and heuristic fit score
3. Optional: click **Enhance with AI** for a richer summary and pitch angle
4. Confirm or edit **Contact email** and click **Save**

## 3. Start engagement (~4 min)

1. Click **Start engagement** to create a client project in `lead` stage
2. Upload the client brief on the project **Documents** page → wait for **Ready**
3. Open **SOW** → generate tiers → copy **portal link**
4. Skim **Requirements** and **Execution** to confirm the pipeline continues

## Success criteria

- [ ] At least one prospect search completed (Celery worker running)
- [ ] CSV export downloads with lead data
- [ ] One prospect converted to a project in `lead` pipeline stage
- [ ] SOW generation runs on uploaded brief
- [ ] Client portal link opens and shows tiers

## Notes

- Business emails are often missing from Places — scrape + manual edit is expected
- Outreach is **manual** in MVP A: export CSV and contact leads in your own email tool
- In-app outreach (Resend drafts) is deferred — backend routes remain for a future release
- Defer for later: Gmail sync, PageSpeed API, automated follow-up sequences
