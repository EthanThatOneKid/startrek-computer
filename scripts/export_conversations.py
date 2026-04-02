#!/usr/bin/env python3
"""
export_conversations.py — Export raw conversations from varenc transcripts.
Run: python -m scripts.export_conversations
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.analyze_conversations import extract_episode_conversations


def main():
    base = Path(__file__).parent.parent / "data" / "raw" / "star_trek_transcript_search" / "scripts"

    out_path = Path(__file__).parent.parent / "data" / "conversations.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    all_convs = []
    for series_dir in sorted(base.iterdir()):
        if not series_dir.is_dir():
            continue
        series_name = series_dir.name
        print(f"  {series_name}: ", end="", flush=True)
        episodes = sorted(series_dir.glob("*.txt"))
        ep_convs = 0
        for ep in episodes:
            convs = extract_episode_conversations(ep)
            for conv in convs:
                conv["series"] = series_name
            all_convs.extend(convs)
            ep_convs += len(convs)
        print(f"{len(episodes)} episodes, {ep_convs} convs")

    out_path.write_text(json.dumps(all_convs, indent=2))
    print(f"\nWrote {len(all_convs)} conversations to {out_path}")


if __name__ == "__main__":
    main()
