# Sample documents for demos

Use any **public-domain** or **licensed** PDF for portfolio demos:

- [SEC EDGAR filings](https://www.sec.gov/edgar/search/) (10-K, 10-Q)
- [Project Gutenberg](https://www.gutenberg.org/) (export or print-to-PDF)
- Wikipedia articles (print to PDF from browser)

## Quick eval setup

1. Upload the sample PDF via the app
2. Wait until status is **Ready**
3. Ask a few questions in chat; note chunk IDs from API logs or DB:
   ```sql
   SELECT id, left(content, 80) FROM chunk WHERE doc_id = '<document-uuid>' LIMIT 10;
   ```
4. Fill `eval/dataset.json` with questions and relevant chunk UUIDs
5. Run `python -m eval.run_eval --user-id <uuid>`
