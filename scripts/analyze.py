#!/usr/bin/env python3
"""
analyze.py — Print stats from the final deduplicated dataset.
Run: python -m scripts.analyze
"""
import json
from pathlib import Path
from typing import List
from collections import Counter, defaultdict
from pydantic import TypeAdapter
from models.spec import Interaction


def main():
    base = Path(__file__).parent.parent
    data_file = base / "data" / "interactions_deduped.json"

    if not data_file.exists():
        print(f"Error: {data_file} not found. Running with interactions.json instead.")
        data_file = base / "data" / "interactions.json"

    if not data_file.exists():
        print("Error: No data files found.")
        return

    adapter = TypeAdapter(List[Interaction])
    interactions = adapter.validate_python(json.loads(data_file.read_text()))
    
    print(f"Total interactions: {len(interactions)}")

    # Series breakdown
    print("\n=== By Series ===")
    series_counts = Counter(i.context.series for i in interactions)
    for series, count in sorted(series_counts.items(), key=lambda x: -x[1]):
        print(f"  {series:15s} {count:4d}  ({100*count/len(interactions):.1f}%)")

    # Intent breakdown
    print("\n=== By Intent ===")
    intent_counts = Counter(i.candidates[0].classification.intent for i in interactions)
    for intent, count in sorted(intent_counts.items(), key=lambda x: -x[1]):
        print(f"  {intent:25s} {count:4d}  ({100*count/len(interactions):.1f}%)")

    # Multi-turn
    multi = [i for i in interactions if i.is_multi_turn]
    print(f"\n=== Multi-turn: {len(multi)} ({100*len(multi)/len(interactions):.1f}%) ===")

    # Avg computer turns
    avg_turns = sum(i.num_computer_turns for i in interactions) / len(interactions) if interactions else 0
    print(f"Avg computer turns per interaction: {avg_turns:.2f}")

    # Confidence stats
    confidences = [i.candidates[0].classification.confidence for i in interactions]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0
    print(f"\nAvg LLM classification confidence: {avg_conf:.2f}")


if __name__ == "__main__":
    main()
