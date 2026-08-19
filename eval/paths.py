"""Shared paths for the eval harness."""

from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = EVAL_DIR / "fixtures"
FIXTURE_STATE_PATH = EVAL_DIR / "fixture_state.json"
DATASETS_DIR = EVAL_DIR / "datasets"
GOLDEN_DATASET_PATH = DATASETS_DIR / "golden.json"
GOLDEN_MARKDOWN_PATH = DATASETS_DIR / "golden.md"
DEFAULT_DATASET_PATH = EVAL_DIR / "dataset.json"
REPORT_PATH = EVAL_DIR / "report.json"
RETRIEVAL_REPORT_PATH = EVAL_DIR / "retrieval_report.json"

EVAL_USER_EMAIL = "eval-harness@shiori.local"
EVAL_PROJECT_NAME = "Eval Harness"
FIXTURE_DOCX_NAME = "agency_sample.docx"
