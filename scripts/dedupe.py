#!/usr/bin/env python3
"""
dedupe.py — Deduplicate classified conversations.
Run: python -m scripts.dedupe
"""
import json
import re
from pathlib import Path
from collections import defaultdict


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
    in_file = base / "data" / "classified.json"
    out_file = base / "data" / "deduplicated.json"

    data = json.loads(in_file.read_text())
    print(f"Loaded {len(data)} classified conversations")

    # ----------------------------------------------------------------
    # Pass 1: exact dedup — same episode + same primary computer response
    # ----------------------------------------------------------------
    seen_exact = set()
    exact_filtered = []
    exact_dupes = 0

    for conv in data:
        turns = conv.get("turns", [])
        primary_response = turns[0].get("computer_response", "") if turns else ""
        key = (conv["series"], conv["episode"], primary_response)
        if key not in seen_exact:
            seen_exact.add(key)
            exact_filtered.append(conv)
        else:
            exact_dupes += 1

    print(f"  Exact dedup: removed {exact_dupes}, kept {len(exact_filtered)}")

    # ----------------------------------------------------------------
    # Pass 2: canonical dedup — same canonical response text
    #   Prefer: highest confidence, multi-turn, shortest query
    # ----------------------------------------------------------------
    canonical_groups = defaultdict(list)
    for conv in exact_filtered:
        turns = conv.get("turns", [])
        primary_response = turns[0].get("computer_response", "") if turns else ""
        key = canonicalize(primary_response)
        if key:
            canonical_groups[key].append(conv)

    canonical_filtered = []
    canonical_dupes = 0

    for key, group in canonical_groups.items():
        if len(group) == 1:
            canonical_filtered.append(group[0])
        else:
            scored = []
            for idx, conv in enumerate(group):
                conf = conv.get("intent_confidence", 0.0)
                num_turns = len([t for t in conv.get("turns", []) if t.get("computer_response")])
                query = conv.get("turns", [{}])[0].get("human_query", "") or ""
                query_len = len(query.split())
                score = (conf, num_turns, -query_len)
                scored.append((score, idx, conv))

            scored.sort(reverse=True)
            canonical_filtered.append(scored[0][2])
            canonical_dupes += len(group) - 1

    print(f"  Canonical dedup: removed {canonical_dupes}, kept {len(canonical_filtered)}")

    # ----------------------------------------------------------------
    # Pass 3: boilerplate — responses appearing >10x across all episodes
    # ----------------------------------------------------------------
    response_counts = defaultdict(int)
    for conv in canonical_filtered:
        for turn in conv.get("turns", []):
            resp = turn.get("computer_response", "")
            if resp:
                response_counts[canonicalize(resp)] += 1

    boilerplate_keys = {k for k, v in response_counts.items() if v > 10}
    boilerplate_filtered = [
        c for c in canonical_filtered
        if not any(
            canonicalize(t.get("computer_response", "")) in boilerplate_keys
            for t in c.get("turns", [])
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

    # Strip context and intent_raw for cleanliness
    for conv in boilerplate_filtered:
        conv.pop("context", None)
        conv.pop("intent_raw", None)
        for turn in conv.get("turns", []):
            turn.pop("line_num", None)
            turn.pop("raw", None)

    stats = {
        "input_total": len(data),
        "output_total": len(boilerplate_filtered),
        "exact_dupes": exact_dupes,
        "canonical_dupes": canonical_dupes,
        "boilerplate_removed": boilerplate_removed,
        "boilerplate_threshold": 10,
        "intent_distribution": {},
    }

    from collections import Counter
    intent_dist = Counter(c.get("intent", "other") for c in boilerplate_filtered)
    stats["intent_distribution"] = dict(intent_dist)

    output = {"stats": stats, "conversations": boilerplate_filtered}
    out_file.write_text(json.dumps(output, indent=2))

    print(f"\n  Total: {stats['output_total']} conversations (from {stats['input_total']})")
    print(f"\nIntent distribution:")
    for intent, count in sorted(intent_dist.items(), key=lambda x: -x[1]):
        print(f"  {intent:25s} {count:4d}  ({100*count/len(boilerplate_filtered):.1f}%)")


if __name__ == "__main__":
    main()
