#!/usr/bin/env python3
"""
Extract "conversations" with the Star Trek computer.
Simpler approach: find every line where the computer speaks,
cluster consecutive computer lines within a gap threshold,
and grab surrounding lines as context.
"""
import re
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

COMPUTER_SPEAK_RE = re.compile(
    r"^(COMPUTER:|COMPUTER VOICE:|\[COMPUTER [A-Z]+\]|[A-Z][A-Z0-9 -]+ COMPUTER VOICE:)",
    re.IGNORECASE,
)


def is_computer_line(line: str) -> bool:
    return bool(COMPUTER_SPEAK_RE.match(line.strip()))


def extract_episode_conversations(episode_path: Path, gap: int = 8) -> list[dict]:
    """
    Extract all computer conversations from a single episode file.
    gap: max lines between computer-related lines to still be the same conversation.
    """
    lines = episode_path.read_text().split("\n")

    # Find all computer-speaking line indices
    computer_indices = [i for i, line in enumerate(lines) if is_computer_line(line)]
    if not computer_indices:
        return []

    # Cluster into conversations by gap threshold
    conversations = []
    current = [computer_indices[0]]
    for idx in computer_indices[1:]:
        if idx - current[-1] <= gap:
            current.append(idx)
        else:
            conversations.append(current)
            current = [idx]
    conversations.append(current)

    result = []
    for conv_indices in conversations:
        start = max(0, conv_indices[0] - 3)
        end = min(len(lines) - 1, conv_indices[-1] + 2)

        context = []
        for i in range(start, end + 1):
            line = lines[i]
            m = re.match(r"^([A-Z][A-Z0-9 '.\-]+):\s*(.*)", line.strip())
            speaker = m.group(1) if m else None
            text = m.group(2) if m else line.strip()
            context.append({
                "line_num": i,
                "speaker": speaker,
                "text": text,
                "is_computer": i in set(conv_indices),
                "raw": line.strip(),
            })

        result.append({
            "episode": episode_path.name,
            "series": episode_path.parent.name,
            "start_line": start,
            "end_line": end,
            "computer_indices": conv_indices,
            "num_computer_turns": len(conv_indices),
            "context": context,
        })

    return result


def main():
    import sys
    base = Path("/home/.z/workspaces/con_7kqzVCCMoRqfIUpd/star_trek_transcript_search/scripts")
    series_name = sys.argv[1] if len(sys.argv) > 1 else "NextGen"
    episode_file = sys.argv[2] if len(sys.argv) > 2 else None

    if episode_file:
        episodes = [base / series_name / episode_file]
    else:
        episodes = sorted((base / series_name).glob("*.txt"))

    all_convs = []
    for ep in episodes:
        convs = extract_episode_conversations(ep)
        all_convs.extend(convs)
        print(f"{ep.name}: {len(convs)} conversations")

    print(f"\nTotal: {len(all_convs)} conversations")
    print("\n--- Sample conversation ---")
    if all_convs:
        sample = all_convs[min(2, len(all_convs) - 1)]
        print(json.dumps(sample, indent=2))


if __name__ == "__main__":
    main()
