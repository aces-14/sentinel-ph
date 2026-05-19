"""
Phase 2 Step 5 — RAG CLI

Interactive terminal chat backed by the LangGraph RAG workflow.

Usage:
    python -m src.rag.cli

Type 'quit' or 'exit' to leave, 'clear' to reset the singleton graph cache.
"""

from __future__ import annotations

import logging
import sys


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(message)s",
    )


def main() -> None:
    _configure_logging()

    # Lazy import so logging is configured first
    from src.rag.chat import ask

    print("SentinelPH Dengue Intelligence Assistant")
    print("Type your question. Enter 'quit' to exit.\n")

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not question:
            continue

        if question.lower() in {"quit", "exit"}:
            print("Bye.")
            break

        print("Thinking…", flush=True)

        try:
            result = ask(question)
        except EnvironmentError as exc:
            print(f"[Error] {exc}\n")
            sys.exit(1)
        except Exception as exc:  # noqa: BLE001
            print(f"[Error] {exc}\n")
            continue

        print(f"\nSentinelPH: {result['answer']}")
        validity = "✓ cited" if result["valid"] else "⚠ uncited claims"
        print(f"  [attempts={result['attempts']}, {validity}]\n")


if __name__ == "__main__":
    main()
