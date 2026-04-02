#!/usr/bin/env python3
"""
analyze.py — Print stats from the final deduplicated dataset.
Run: python -m scripts.analyze
"""
import json
from pathlib import Path
from collections import Counter, defaultdict


def main():
    base = Path(__file__).parent.parent
    data_file = base / "data" / "deduplicated.json"

    data = json.loads(data_file.read_text())
    if isinstance(data, list):
        convs = data
        stats = {}
    else:
        convs = data.get("conversations", [])
        stats = data.get("stats", {})

    print(f"Total conversations: {len(convs)}")

    # Series breakdown
    print("\n=== By Series ===")
    series_counts = Counter(c.get("series", "unknown") for c in convs)
    for series, count in sorted(series_counts.items(), key=lambda x: -x[1]):
        print(f"  {series:15s} {count:4d}  ({100*count/len(convs):.1f}%)")

    # Intent breakdown
    print("\n=== By Intent ===")
    intent_counts = Counter(c.get("intent", "unknown") for c in convs)
    for intent, count in sorted(intent_counts.items(), key=lambda x: -x[1]):
        print(f"  {intent:25s} {count:4d}  ({100*count/len(convs):.1f}%)")

    # Multi-turn
    multi = [c for c in convs if c.get("is_multi_turn", False)]
    print(f"\n=== Multi-turn: {len(multi)} ({100*len(multi)/len(convs):.1f}%) ===")

    # Avg computer turns
    avg_turns = sum(c.get("num_computer_turns", 0) for c in convs) / len(convs) if convs else 0
    print(f"Avg computer turns per conversation: {avg_turns:.2f}")

    # Confidence stats
    confidences = [c.get("intent_confidence", 0) for c in convs]
    avg_conf = sum(c for c in confidences if c) / len([c for c in confidences if c]) if confidences else 0
    print(f"\nAvg LLM classification confidence: {avg_conf:.2f}")

    # Dupe stats
    if stats:
        print(f"\n=== Dedupe Stats ===")
        for k, v in stats.items():
            if k != "intent_distribution":
                print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
