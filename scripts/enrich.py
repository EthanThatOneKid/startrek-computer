#!/usr/bin/env python3
"""
enrich.py — Add metadata, turn analysis, and query extraction.
Run: python -m scripts.enrich
"""
import json
import re
from pathlib import Path
from typing import Optional

# -------------------------------------------------------------------
# Episode metadata
# -------------------------------------------------------------------

SERIES_METADATA = {
    "NextGen": {
        "seasons": {
            1: list(range(101, 127)),
            2: list(range(135, 162)),
            3: list(range(169, 196)),
            4: list(range(201, 228)),
            5: list(range(235, 262)),
            6: list(range(269, 296)),
            7: list(range(301, 328)),
        },
    },
    "DS9": {
        "seasons": {
            1: list(range(401, 416)),
            2: list(range(417, 440)),
            3: list(range(441, 465)),
            4: list(range(465, 489)),
            5: list(range(489, 513)),
            6: list(range(513, 537)),
            7: list(range(537, 561)),
        },
    },
    "Voyager": {
        "seasons": {
            1: list(range(100, 121)),
            2: list(range(121, 145)),
            3: list(range(145, 170)),
            4: list(range(170, 195)),
            5: list(range(195, 221)),
            6: list(range(221, 246)),
            7: list(range(246, 271)),
        },
    },
    "TOS": {
        "seasons": {1: list(range(1, 17)), 2: list(range(17, 31)), 3: list(range(31, 46))},
    },
    "Discovery": {
        "seasons": {
            1: list(range(301, 315)),
            2: list(range(315, 329)),
            3: list(range(329, 343)),
            4: list(range(343, 357)),
        },
    },
    "Enterprise": {
        "seasons": {
            1: list(range(148, 162)),
            2: list(range(162, 177)),
            3: list(range(177, 192)),
            4: list(range(192, 207)),
        },
    },
    "TAS": {
        "seasons": {1: list(range(1, 17)), 2: list(range(17, 23))},
    },
    "Movies": {"seasons": {}},
}

SERIES_TITLE = {
    "NextGen": "Star Trek: The Next Generation",
    "DS9": "Star Trek: Deep Space Nine",
    "Voyager": "Star Trek: Voyager",
    "TOS": "Star Trek: The Original Series",
    "Discovery": "Star Trek: Discovery",
    "Enterprise": "Star Trek: Enterprise",
    "TAS": "Star Trek: The Animated Series",
    "Movies": "Star Trek Films",
}


def get_episode_num(filename: str) -> Optional[int]:
    base = Path(filename).stem
    digits = re.sub(r"\D", "", base)
    return int(digits) if digits else None


def get_season(series: str, episode_num: int) -> Optional[int]:
    meta = SERIES_METADATA.get(series)
    if not meta or not meta["seasons"]:
        return None
    for season, codes in meta["seasons"].items():
        if episode_num in codes:
            return season
    return None


def extract_stardate(episode_path: Path) -> Optional[str]:
    try:
        for line in episode_path.read_text().split("\n")[:30]:
            m = re.search(r"Stardate\s+(\d+\.?\d*)", line, re.IGNORECASE)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None


def _human_lines_before_computer(context: list[dict], computer_ln: int) -> list[str]:
    """
    Collect non-computer, non-stage-direction lines between the previous
    computer turn and the current one. Falls back to last 10 lines if
    no previous computer turn exists.
    """
    # Find previous computer line number
    prev_ln = 0
    for e in context:
        if e.get("is_computer") and e["line_num"] < computer_ln:
            prev_ln = e["line_num"]

    start = prev_ln + 1 if prev_ln else max(0, computer_ln - 10)
    lines = []
    for e in context:
        ln = e["line_num"]
        if start <= ln < computer_ln:
            speaker = e.get("speaker")
            text = (e.get("text") or "").strip()
            if text and not e.get("is_computer") and speaker is not None:
                lines.append(text)
    return lines


def enrich_conversation(conv: dict, episode_path: Path) -> dict:
    """Add metadata, turn analysis, and per-turn query/response pairs."""
    series = conv["series"]
    episode = conv["episode"]
    context: list[dict] = conv.get("context", [])
    ep_num = get_episode_num(episode)
    season = get_season(series, ep_num) if ep_num else None

    # Collect computer entries and human context per turn
    turns = []
    human_speakers: set[str] = set()

    for entry in context:
        if not entry.get("is_computer"):
            continue
        cln = entry["line_num"]
        comp_text = (entry.get("text") or "").strip()
        human_lines = _human_lines_before_computer(context, cln)

        for hl in human_lines:
            speaker = hl.split(":")[0].strip()
            if speaker:
                human_speakers.add(speaker)

        turns.append(
            {
                "computer_response": comp_text,
                "human_query": human_lines[0] if human_lines else "",
                "human_query_context": " ".join(human_lines),
                "line_num": cln,
            }
        )

    is_multi_turn = len(turns) > 1
    computer_responses = [t["computer_response"] for t in turns]
    human_queries = [t["human_query"] for t in turns]
    primary_query = turns[0] if turns else {}

    return {
        "episode": episode,
        "series": series,
        "series_title": SERIES_TITLE.get(series, series),
        "season": season or 0,
        "episode_num": ep_num or 0,
        "start_line": conv["start_line"],
        "end_line": conv["end_line"],
        "is_multi_turn": is_multi_turn,
        "num_human_turns": len(human_speakers),
        "num_computer_turns": len(turns),
        "stardate": extract_stardate(episode_path) or "",
        # Flat arrays (used by classify + dedupe)
        "computer_responses": computer_responses,
        "human_queries": human_queries,
        # Primary query (convenience field)
        "query": primary_query.get("human_query", ""),
        # Nested turns for full detail
        "turns": turns,
        # Keep context for debugging (dedupe.py strips it)
        "context": context,
    }


def main():
    base = Path(__file__).parent.parent
    raw_path = base / "data" / "conversations.json"
    out_path = base / "data" / "enriched.json"
    scripts_base = base / "data" / "raw" / "star_trek_transcript_search" / "scripts"

    data = json.loads(raw_path.read_text())
    print(f"Loaded {len(data)} raw conversations")

    errors = 0
    multi_turn = 0

    for i, conv in enumerate(data):
        ep_path = scripts_base / conv["series"] / conv["episode"]
        try:
            data[i] = enrich_conversation(conv, ep_path)
            if data[i]["is_multi_turn"]:
                multi_turn += 1
        except Exception as e:
            errors += 1
            print(f"  ERROR {conv['episode']}: {e}")

        if (i + 1) % 200 == 0:
            print(f"  Processed {i + 1}/{len(data)}")

    print(
        f"\nWrote {len(data) - errors} enriched conversations to {out_path}"
        f"\n  Multi-turn: {multi_turn} ({100*multi_turn/len(data):.1f}%)"
        f"\n  Errors: {errors}"
    )
    out_path.write_text(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
