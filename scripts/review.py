#!/usr/bin/env python3
"""
review.py — Re-classify conversations via OpenRouter LLM.
For QA: by episode, intent, or random sample.
Run: python -m scripts.review --episode 100101.txt
       python -m scripts.review --intent warning_alert --random 5
       python -m scripts.review --all
"""
import json
import os
import sys
import urllib.request
import urllib.error
import time
import argparse
import random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
MODEL = "openrouter/free"
SITE_URL = "https://github.com/EthanThatOneKid/startrek-computer"
SITE_NAME = "startrek-computer"

INTENTS = [
    "information_retrieval", "system_control", "warning_alert",
    "environmental", "holodeck", "medical", "navigation", "security", "other",
]

SYSTEM_PROMPT = (
    "You are an expert annotator for Star Trek computer interactions. "
    "Classify each conversation by the PRIMARY intent of the computer's response(s). "
    "Choose ONE from: " + ", ".join(INTENTS) + ". "
    "Be strict -- pick the single best label."
)

USER_PROMPT_TEMPLATE = (
    'Classify this Star Trek computer interaction.\n\nSeries: {series}\nEpisode: {episode}\n'
    'Computer responses: "{computer_response}"\nHuman queries: "{human_query}"\n\n'
    "Respond with ONLY a JSON object: {\"intent\": \"<label>\", \"confidence\": <0.0-1.0>}"
)


def call_llm(computer_response: str, human_query: str, series: str, episode: str) -> dict:
    user_prompt = USER_PROMPT_TEMPLATE.format(
        series=series, episode=episode,
        computer_response=computer_response[:300], human_query=human_query[:200],
    )
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 64,
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": SITE_URL,
        "X-Title": SITE_NAME,
    }
    body = json.dumps(payload).encode()
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=body, headers=headers, method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data_raw = json.loads(resp.read())
                content = data_raw["choices"][0]["message"]["content"].strip()
            result = json.loads(content)
            return {
                "intent": result.get("intent", "other"),
                "confidence": float(result.get("confidence", 0.5)),
            }
        except Exception as e:
            if "429" in str(e):
                time.sleep(10 * (attempt + 1))
            else:
                return {"intent": "other", "confidence": 0.0}
    return {"intent": "other", "confidence": 0.0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", help="Re-classify specific episode file")
    parser.add_argument("--intent", help="Re-classify all with given intent")
    parser.add_argument("--random", type=int, metavar="N", help="Re-classify N random conversations")
    parser.add_argument("--all", action="store_true", help="Re-classify ALL conversations")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not API_KEY:
        print("ERROR: OPENROUTER_API_KEY not set")
        sys.exit(1)

    base = Path(__file__).parent.parent
    classified_file = base / "data" / "classified.json"
    data = json.loads(classified_file.read_text())

    if args.episode:
        subset = [c for c in data if c.get("episode") == args.episode]
        print(f"Episode {args.episode}: {len(subset)} conversations")
    elif args.intent:
        subset = [c for c in data if c.get("intent") == args.intent]
        print(f"Intent={args.intent}: {len(subset)} conversations")
    elif args.random:
        subset = random.sample(data, min(args.random, len(data)))
        print(f"Random sample: {len(subset)}")
    elif args.all:
        subset = data
        print(f"All: {len(subset)} conversations")
    else:
        print("ERROR: specify --episode, --intent, --random, or --all")
        sys.exit(1)

    if args.dry_run:
        for c in subset:
            print(f"  {c.get('series')}/{c.get('episode')}  intent={c.get('intent')}  "
                  f"conf={c.get('intent_confidence', '?')}")
        print(f"\nDry run -- {len(subset)} would be re-classified.")
        return

    print(f"Re-classifying {len(subset)}...")

    def classify_task(conv):
        turns = conv.get("turns", [])
        cr = turns[0].get("computer_response", "") if turns else ""
        hq = turns[0].get("human_query", "") if turns else ""
        return call_llm(cr, hq, conv.get("series", ""), conv.get("episode", ""))

    updated = 0
    done = 0
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(classify_task, c): c for c in subset}
        for future in as_completed(futures):
            conv = futures[future]
            try:
                result = future.result()
                old = conv.get("intent")
                new = result["intent"]
                conv["intent"] = new
                conv["intent_confidence"] = result["confidence"]
                changed = ""
                print(f"  {conv.get('episode'):15s}  {old:25s} -> {new:25s}  conf={result['confidence']:.2f}  {changed}")
                updated += 1
            except Exception as e:
                print(f"  ERROR {conv.get('episode')}: {e}")
            done += 1
            if done % 50 == 0:
                print(f"  ... {done}/{len(subset)}")

    classified_file.write_text(json.dumps(data, indent=2))
    print(f"\nUpdated {updated}/{len(subset)} in {classified_file}")


if __name__ == "__main__":
    main()
