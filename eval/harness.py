#!/usr/bin/env python3
"""Unified CLI for the RAG eval harness."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.generate_dataset import generate_dataset
from eval.run_agent_eval import main as agent_main
from eval.run_retrieval_eval import main as retrieval_main
from eval.seed_fixtures import seed_fixtures


def _run_seed(force: bool) -> None:
    import asyncio

    asyncio.run(seed_fixtures(force=force))


def _run_generate(count: int, refine: bool) -> None:
    import asyncio

    asyncio.run(generate_dataset(count=count, refine=refine))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RAG eval harness")
    sub = parser.add_subparsers(dest="command", required=True)

    seed_parser = sub.add_parser("seed", help="Ingest eval fixture document")
    seed_parser.add_argument("--force", action="store_true")

    gen_parser = sub.add_parser("generate", help="LLM-generate golden dataset")
    gen_parser.add_argument("--count", type=int, default=10)
    gen_parser.add_argument("--refine", action="store_true")

    retrieval_parser = sub.add_parser("retrieval", help="Run retrieval eval")
    retrieval_parser.add_argument("--compare", action="store_true")
    retrieval_parser.add_argument("--hybrid", action="store_true")
    retrieval_parser.add_argument("--min-recall", type=float, default=None)
    retrieval_parser.add_argument("--k", type=int, default=5)

    sub.add_parser("agent", help="Run end-to-end agent eval")

    all_parser = sub.add_parser("all", help="seed → generate → retrieval → agent")
    all_parser.add_argument("--force", action="store_true")
    all_parser.add_argument("--count", type=int, default=10)
    all_parser.add_argument("--refine", action="store_true")
    all_parser.add_argument("--min-recall", type=float, default=None)

    args = parser.parse_args(argv)

    if args.command == "seed":
        _run_seed(force=args.force)
        return 0

    if args.command == "generate":
        _run_generate(count=args.count, refine=args.refine)
        return 0

    if args.command == "retrieval":
        retrieval_argv = []
        if args.compare:
            retrieval_argv.append("--compare")
        if args.hybrid:
            retrieval_argv.append("--hybrid")
        if args.min_recall is not None:
            retrieval_argv.extend(["--min-recall", str(args.min_recall)])
        retrieval_argv.extend(["--k", str(args.k)])
        return retrieval_main(retrieval_argv)

    if args.command == "agent":
        return agent_main([])

    if args.command == "all":
        _run_seed(force=args.force)
        _run_generate(count=args.count, refine=args.refine)
        code = retrieval_main(["--compare"])
        if code != 0:
            return code
        return agent_main([])

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
