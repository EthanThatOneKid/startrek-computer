#!/usr/bin/env python3
"""
run_pipeline.py — Run the full preprocessing pipeline.
Each step is idempotent; re-run any step without re-running prior ones.
"""
import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    ("export_conversations", "Extracting raw conversations..."),
    ("enrich",              "Enriching with metadata..."),
    ("classify",            "Classifying intents..."),
    ("dedupe",              "Deduplicating..."),
    ("analyze",             "Analyzing & generating stats..."),
]

BASE = Path(__file__).parent.parent


def run(script_name: str, label: str) -> None:
    print(f"\n{'='*50}")
    print(f"{label}")
    print(f"{'='*50}")
    result = subprocess.run(
        [sys.executable, "-m", f"scripts.{script_name}"],
        cwd=BASE,
    )
    if result.returncode != 0:
        print(f"FAILED: {script_name} (exit {result.returncode})")
        sys.exit(result.returncode)
    print(f"OK")


def main():
    for script, label in SCRIPTS:
        run(script, label)

    print(f"\n{'='*50}")
    print("Pipeline complete! 🎉")
    print(f"{'='*50}")
    print(f"\nOutputs in data/:")
    for f in sorted((BASE / "data").glob("*")):
        print(f"  data/{f.name}")


if __name__ == "__main__":
    main()
