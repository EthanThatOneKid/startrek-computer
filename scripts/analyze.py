#!/usr/bin/env python3
"""
analyze.py — Generate stats.md from the final dataset.
Run: python -m scripts.analyze
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from datetime import date


SERIES_DISPLAY = {
    "NextGen": "Star Trek: The Next Generation",
    "DS9": "Star Trek: Deep Space Nine",
    "Voyager": "Star Trek: Voyager",
    "TOS": "Star Trek: The Original Series",
    "Discovery": "Star Trek: Discovery",
    "Enterprise": "Star Trek: Enterprise",
    "TAS": "Star Trek: The Animated Series",
    "Movies": "Star Trek Films",
}


def word_count(text: str) -> int:
    if not text:
        return 0
    return len(text.split())


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * p / 100)
    idx = min(idx, len(sorted_vals) - 1)
    return sorted_vals[idx]


def main():
    base_dir = Path(__file__).parent.parent
    dataset_file = base_dir / "data" / "dataset.json"

    if not dataset_file.exists():
        print("ERROR: data/dataset.json not found. Run dedupe.py first.")
        return

    conversations = json.loads(dataset_file.read_text())
    print(f"Loaded {len(conversations)} dataset conversations")

    # ── Basic counts ────────────────────────────────────────────────
    total = len(conversations)

    # ── By series ───────────────────────────────────────────────────
    by_series: dict[str, list[dict]] = defaultdict(list)
    for conv in conversations:
        by_series[conv["series"]].append(conv)

    # ── By intent ───────────────────────────────────────────────────
    intent_counts: dict[str, int] = Counter(c["primary_intent"] for c in conversations)
    intent_pct = {k: round(100 * v / total, 1) for k, v in intent_counts.most_common()}

    # ── Word counts ─────────────────────────────────────────────────
    computer_wc = []
    human_wc = []
    for conv in conversations:
        for resp in conv.get("_raw_computer_wc", []):
            if resp is not None:
                computer_wc.append(float(resp))
        for query in conv.get("human_queries", []):
            if query:
                human_wc.append(float(word_count(query)))

    # ── Multi-turn rate ─────────────────────────────────────────────
    multi_turn = sum(1 for c in conversations if c.get("is_multi_turn"))
    multi_pct = round(100 * multi_turn / total, 1)

    # ── Repeated responses ───────────────────────────────────────────
    response_texts = []
    for conv in conversations:
        for resp in conv.get("_raw_computer_texts", []):
            if resp:
                response_texts.append(resp.lower())

    response_counter = Counter(response_texts)
    repeats = [(t, c) for t, c in response_counter.most_common() if c > 1]

    # ── Build stats dict ────────────────────────────────────────────
    stats = {
        "total": total,
        "by_series": {s: len(v) for s, v in sorted(by_series.items())},
        "intent_distribution": dict(intent_counts.most_common()),
        "intent_pct": intent_pct,
        "computer_wc": {
            "mean": round(sum(computer_wc) / len(computer_wc), 2) if computer_wc else 0,
            "median": percentile(computer_wc, 50),
            "p90": percentile(computer_wc, 90),
            "max": max(computer_wc) if computer_wc else 0,
            "min": min(computer_wc) if computer_wc else 0,
        },
        "human_wc": {
            "mean": round(sum(human_wc) / len(human_wc), 2) if human_wc else 0,
            "median": percentile(human_wc, 50),
            "p90": percentile(human_wc, 90),
            "max": max(human_wc) if human_wc else 0,
        },
        "multi_turn_pct": multi_pct,
        "repeated_responses": repeats[:20],
    }

    # ── Write stats.json ───────────────────────────────────────────
    stats_file = base_dir / "data" / "stats.json"
    stats_file.write_text(json.dumps(stats, indent=2))

    # ── Generate stats.md ──────────────────────────────────────────
    today = date.today().isoformat()

    md_lines = [
        "# Star Trek Computer — Dataset Statistics",
        f"",
        f"_Generated {today}_",
        "",
        "## Overview",
        "",
        f"- **Total unique conversations:** {total}",
        f"- **Multi-turn exchanges:** {multi_turn} ({multi_pct}%)",
        f"- **Series covered:** {len(by_series)}",
        "",
        "## Computer Response Length (words)",
        "",
        f"- Mean: {stats['computer_wc']['mean']}",
        f"- Median: {stats['computer_wc']['median']}",
        f"- 90th percentile: {stats['computer_wc']['p90']}",
        f"- Range: {stats['computer_wc']['min']} – {stats['computer_wc']['max']}",
        "",
        "## Human Query Length (words)",
        "",
        f"- Mean: {stats['human_wc']['mean']}",
        f"- Median: {stats['human_wc']['median']}",
        f"- 90th percentile: {stats['human_wc']['p90']}",
        "",
        "## Intent Distribution",
        "",
    ]

    for intent, count in intent_counts.most_common():
        md_lines.append(f"- **{intent}** — {count} ({intent_pct[intent]}%)")

    md_lines += [
        "",
        "## By Series",
        "",
        "| Series | Conversations |",
        "|--------|---------------|",
    ]

    for series, count in sorted(stats["by_series"].items(), key=lambda x: -x[1]):
        label = SERIES_DISPLAY.get(series, series)
        md_lines.append(f"| {label} | {count} |")

    md_lines += [
        "",
        "## Top Repeated Responses (potential boilerplate)",
        "",
        "| Count | Response (first 80 chars) |",
        "|-------|----------------------------|",
    ]

    for resp, count in repeats[:15]:
        snippet = resp[:80].replace("|", "\\|")
        md_lines.append(f"| {count}x | {snippet} |")

    md_lines.append("")
    stats_md_file = base_dir / "data" / "stats.md"
    stats_md_file.write_text("\n".join(md_lines))
    print(f"Wrote {stats_md_file}")


if __name__ == "__main__":
    main()
