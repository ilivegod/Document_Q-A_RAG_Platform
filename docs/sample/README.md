# Sample documents for demos

Use any **public-domain** or **licensed** PDF for portfolio demos:

- [SEC EDGAR filings](https://www.sec.gov/edgar/search/) (10-K, 10-Q)
- [Project Gutenberg](https://www.gutenberg.org/) (export or print-to-PDF)
- Wikipedia articles (print to PDF from browser)

## Automated eval harness (recommended)

The repo includes a deterministic agency brief fixture and harness — no manual SQL for chunk IDs:

```bash
cd Document_Q&A_RAG_Platform
python -m eval.harness seed
python -m eval.harness generate --count 10
python -m eval.harness retrieval --compare
python -m eval.harness agent
```

See root `README.md` for full harness documentation.

## Manual eval (legacy)

1. Upload a sample PDF via the app
2. Wait until status is **Ready**
3. Fill `eval/dataset.json` with questions and relevant chunk UUIDs
4. Run `python -m eval.run_eval --user-id <uuid>`
