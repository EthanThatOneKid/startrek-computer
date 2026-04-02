#!/usr/bin/env python3
"""
dedupe.py — Deduplicate computer conversations.
Run: python -m scripts.dedupe
"""
import json
import re
from collections import defaultdict
from pathlib import Path


def canonicalize(text: str) -> str:
    """Normalize text for comparison: lowercase, strip punct, normalize whitespace."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _score(conv: dict) -> tuple[int, int]:
    """
    Higher = better. Multi-turn conversations rank higher;
    shorter human query ranks higher (more reusable/generalizable).
    """
    is_multi = 1 if conv.get("is_multi_turn") else 0
    query = (conv.get("human_queries") or [""])[0] or ""
    query_words = len(query.split()) if query else 999
    return (is_multi, -query_words)


def deduplicate(conversations: list[dict]) -> tuple[list[dict], dict]:
    """
    Deduplicate in three passes:
    1. Exact dedup  — identical (series, episode, computer_responses) tuple
    2. Canonical dedup — same canonical response text; prefer multi-turn + shortest query
    3. Boilerplate   — responses appearing >10 times across all episodes
    """

    # ----------------------------------------------------------------
    # Pass 1: Exact dedup
    # ----------------------------------------------------------------
    seen_exact: set[tuple] = set()
    exact_filtered = []
    exact_dupes = 0

    for conv in conversations:
        key = (
            conv["series"],
            conv["episode"],
            tuple(conv.get("computer_responses", [])),
        )
        if key not in seen_exact:
            seen_exact.add(key)
            exact_filtered.append(conv)
        else:
            exact_dupes += 1

    print(f"  Exact dedup: removed {exact_dupes}, kept {len(exact_filtered)}")

    # ----------------------------------------------------------------
    # Pass 2: Canonical dedup
    # ----------------------------------------------------------------
    canonical_groups: dict[str, list[dict]] = defaultdict(list)
    for conv in exact_filtered:
        resp = (conv.get("computer_responses") or [""])[0] or ""
        key = canonicalize(resp)
        if key:
            canonical_groups[key].append(conv)

    canonical_filtered = []
    canonical_dupes = 0

    for key, group in canonical_groups.items():
        if len(group) == 1:
            canonical_filtered.append(group[0])
        else:
            # Sort by score descending; keep first
            group.sort(key=_score, reverse=True)
            canonical_filtered.append(group[0])
            canonical_dupes += len(group) - 1

    print(f"  Canonical dedup: removed {canonical_dupes}, kept {len(canonical_filtered)}")

    # ----------------------------------------------------------------
    # Pass 3: Boilerplate — response appears >10 times across all episodes
    # ----------------------------------------------------------------
    response_counts: dict[str, int] = defaultdict(int)
    for conv in canonical_filtered:
        for resp in conv.get("computer_responses", []):
            if resp:
                response_counts[canonicalize(resp)] += 1

    boilerplate_keys = {k for k, v in response_counts.items() if v > 10}

    boilerplate_filtered = []
    boilerplate_removed = 0
    for conv in canonical_filtered:
        primary = canonicalize((conv.get("computer_responses") or [""])[0] or "")
        if primary in boilerplate_keys:
            boilerplate_removed += 1
        else:
            boilerplate_filtered.append(conv)

    print(
        f"  Boilerplate (>{10}x): removed {boilerplate_removed},"
        f" kept {len(boilerplate_filtered)}"
    )

    result = {
        "total_input": len(conversations),
        "total_output": len(boilerplate_filtered),
        "exact_dupes": exact_dupes,
        "canonical_dupes": canonical_dupes,
        "boilerplate_removed": boilerplate_removed,
        "boilerplate_responses": [
            (resp, count)
            for resp, count in sorted(response_counts.items(), key=lambda x: -x[1])
            if count > 10
        ],
    }
    return boilerplate_filtered, result


def main():
    classified_path = Path(__file__).parent.parent / "data" / "classified.json"
    out_path = Path(__file__).parent.parent / "data" / "deduplicated.json"

    data = json.loads(classified_path.read_text())
    print(f"Loaded {len(data)} classified conversations")

    # Strip full context (too large) and keep only what we need
    stripped = []
    for conv in data:
        stripped.append(
            {
                "episode": conv["episode"],
                "series": conv["series"],
                "series_title": conv.get("series_title", conv["series"]),
                "season": conv.get("season", 0),
                "episode_num": conv.get("episode_num", 0),
                "stardate": conv.get("stardate", ""),
                "is_multi_turn": conv.get("is_multi_turn", False),
                "num_human_turns": conv.get("num_human_turns", 0),
                "num_computer_turns": conv.get("num_computer_turns", 0),
                "intent": conv.get("intent", "UNKNOWN"),
                "human_queries": conv.get("human_queries", []),
                "computer_responses": conv.get("computer_responses", []),
                "query": conv.get("query", {}),
            }
        )

    cleaned, result = deduplicate(stripped)

    out_path.write_text(json.dumps({"stats": result, "conversations": cleaned}, indent=2))
    print(f"\nWrote {len(cleaned)} deduplicated conversations to {out_path}")
    print(f"\nBoilerplate responses ({len(result['boilerplate_responses'])} total):")
    for resp, count in result["boilerplate_responses"][:10]:
        print(f"  [{count}x] {resp[:60]}")


if __name__ == "__main__":
    main()
