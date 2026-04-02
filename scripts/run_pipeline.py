#!/usr/bin/env python3
"""
run_pipeline.py — Run the full preprocessing pipeline.

Each step is idempotent and can be run independently.
Prerequisites: data/raw/star_trek_transcript_search must be populated
  (git submodule update --init if cloning fresh).

Run: python -m scripts.run_pipeline
"""
import subprocess
from pathlib import Path

BASE = Path(__file__).parent.parent
STEPS = [
    ("Export conversations", ["python", "-m", "scripts.export_conversations"]),
    ("Enrich with metadata", ["python", "-m", "scripts.enrich"]),
    ("Classify intents",    ["python", "-m", "scripts.classify"]),
    ("Deduplicate",         ["python", "-m", "scripts.dedupe"]),
    ("Generate stats",       ["python", "-m", "scripts.analyze"]),
]

def run():
    for i, (label, cmd) in enumerate(STEPS, 1):
        print(f"\n[{i}/{len(STEPS)}] {label}...")
        result = subprocess.run(cmd, cwd=BASE)
        if result.returncode != 0:
            print(f"FAILED — exit code {result.returncode}")
            break
    else:
        print("\nPipeline complete. Output: data/deduplicated.json")

if __name__ == "__main__":
    run()
