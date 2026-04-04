#!/usr/bin/env python3
"""
dedupe.py — Deduplicate classified conversations.
Run: python -m scripts.dedupe
"""
import json, re
from pathlib import Path
from typing import List
from collections import defaultdict, Counter
from pydantic import TypeAdapter
from models.spec import Interaction, Dataset


def canonicalize(text: str) -> str:
    """Normalize text for comparison."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    base = Path(__file__).parent.parent
    in_file = base / "data" / "interactions.json"
    out_file = base / "data" / "interactions_deduped.json"

    if not in_file.exists():
        print(f"Error: {in_file} not found.")
        return

    adapter = TypeAdapter(List[Interaction])
    data = adapter.validate_python(json.loads(in_file.read_text()))
    print(f"Loaded {len(data)} interactions")

    # ----------------------------------------------------------------
    # Pass 1: exact dedup — same episode + same primary computer response
    # ----------------------------------------------------------------
    seen_exact = set()
    exact_filtered = []
    exact_dupes = 0

    for interaction in data:
        primary_response = interaction.candidates[0].content if interaction.candidates else ""
        key = (interaction.context.series, interaction.context.episode, primary_response)
        if key not in seen_exact:
            seen_exact.add(key)
            exact_filtered.append(interaction)
        else:
            exact_dupes += 1

    print(f"  Exact dedup: removed {exact_dupes}, kept {len(exact_filtered)}")

    # ----------------------------------------------------------------
    # Pass 2: canonical dedup — same canonical response text
    #   Prefer: highest confidence, multi-turn, shortest query
    # ----------------------------------------------------------------
    canonical_groups = defaultdict(list)
    for interaction in exact_filtered:
        primary_response = interaction.candidates[0].content if interaction.candidates else ""
        key = canonicalize(primary_response)
        if key:
            canonical_groups[key].append(interaction)

    canonical_filtered = []
    canonical_dupes = 0

    for key, group in canonical_groups.items():
        if len(group) == 1:
            canonical_filtered.append(group[0])
        else:
            scored = []
            for idx, interaction in enumerate(group):
                classification = interaction.candidates[0].classification
                conf = classification.confidence
                num_turns = interaction.num_computer_turns
                query = interaction.transcript[0].text if interaction.transcript else ""
                query_len = len(query.split())
                score = (conf, num_turns, -query_len)
                scored.append((score, idx, interaction))

            scored.sort(reverse=True)
            canonical_filtered.append(scored[0][2])
            canonical_dupes += len(group) - 1

    print(f"  Canonical dedup: removed {canonical_dupes}, kept {len(canonical_filtered)}")

    # ----------------------------------------------------------------
    # Pass 3: boilerplate — responses appearing >10x across all episodes
    # ----------------------------------------------------------------
    response_counts = defaultdict(int)
    for interaction in canonical_filtered:
        for candidate in interaction.candidates:
            resp = candidate.content
            if resp:
                response_counts[canonicalize(resp)] += 1

    boilerplate_keys = {k for k, v in response_counts.items() if v > 10}
    boilerplate_filtered = [
        interaction for interaction in canonical_filtered
        if not any(
            canonicalize(candidate.content) in boilerplate_keys
            for candidate in interaction.candidates
        )
    ]
    boilerplate_removed = len(canonical_filtered) - len(boilerplate_filtered)

    if boilerplate_removed:
        boilerplate_list = [(k, v) for k, v in response_counts.items() if v > 10]
        boilerplate_list.sort(key=lambda x: -x[1])
        print(f"  Boilerplate: removed {boilerplate_removed}")
        for bp, count in boilerplate_list[:5]:
            print(f"    [{count}x] {bp[:60]}")
    else:
        print(f"  Boilerplate: none found")

    # Note: We keep the Interaction model intact (no more popping fields)
    
    stats = {
        "input_total": len(data),
        "output_total": len(boilerplate_filtered),
        "exact_dupes": exact_dupes,
        "canonical_dupes": canonical_dupes,
        "boilerplate_removed": boilerplate_removed,
        "boilerplate_threshold": 10,
        "intent_distribution": {},
    }

    intent_dist = Counter(interaction.candidates[0].classification.intent for interaction in boilerplate_filtered)
    stats["intent_distribution"] = dict(intent_dist)

    # Save as interactions list
    out_file.write_text(json.dumps([idx.model_dump() for idx in boilerplate_filtered], indent=2))

    print(f"\n  Total: {stats['output_total']} interactions (from {stats['input_total']})")
    print(f"\nIntent distribution:")
    for intent, count in sorted(intent_dist.items(), key=lambda x: -x[1]):
        print(f"  {intent:25s} {count:4d}  ({100*count/len(boilerplate_filtered):.1f}%)")


if __name__ == "__main__":
    main()
