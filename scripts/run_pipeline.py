#!/usr/bin/env python3
"""
run_pipeline.py — Run the full preprocessing pipeline.
Run: python -m scripts.run_pipeline
"""
import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    ("export_conversations", "Export raw conversations from transcripts"),
    ("classify_llm",        "Classify all conversations via OpenRouter LLM + build fine-tuning JSONL"),
    ("dedupe",              "Deduplicate and strip context"),
    ("analyze",             "Print final stats"),
]


def run(script: str, description: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"{'='*60}")
    result = subprocess.run([sys.executable, "-m", f"scripts.{script}"])
    if result.returncode != 0:
        print(f"FAILED — exiting")
        raise SystemExit(result.returncode)


def main():
    for script, desc in SCRIPTS:
        run(script, desc)
    print("\n✅ Pipeline complete!")


if __name__ == "__main__":
    main()
