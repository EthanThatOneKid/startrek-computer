#!/usr/bin/env python3
"""
export_conversations.py — Export all raw conversations to JSON.
Run: python -m scripts.export_conversations
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from analyze_conversations import extract_episode_conversations

BASE = Path("data/raw/star_trek_transcript_search/scripts")
OUT = Path("data/conversations.json")

SERIES = ["NextGen", "DS9", "Voyager", "TOS", "Discovery", "Enterprise", "TAS", "Movies"]


def main():
    all_convs = []
    total_eps = 0

    for series in SERIES:
        series_dir = BASE / series
        if not series_dir.exists():
            print(f"WARNING: {series_dir} not found — skipping")
            continue

        episodes = sorted(series_dir.glob("*.txt"))
        total_eps += len(episodes)

        for ep in episodes:
            convs = extract_episode_conversations(ep)
            all_convs.extend(convs)

        print(f"  {series}: {len(episodes)} episodes, {len([c for c in all_convs if c['series'] == series])} convs")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(__import__("json").dumps(all_convs, indent=2))
    print(f"\nWrote {len(all_convs)} conversations to {OUT}")


if __name__ == "__main__":
    main()
