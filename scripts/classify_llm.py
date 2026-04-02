#!/usr/bin/env python3
"""
classify_llm.py — Classify ALL conversations via Zo LLM.
Each conversation gets: intent, confidence, situation, computer_action, notable_phrase.
Output: classified.json + fine_tune.jsonl
"""
import json, time, os, re
from collections import Counter
from pathlib import Path
import urllib.request

INTENTS = ["information_retrieval", "system_control", "warning_alert",
           "environmental", "holodeck", "medical", "navigation", "security", "other"]

SYSTEM = (
    "You are an expert annotator of Star Trek computer interactions.\n"
    "Choose ONE intent from: " + ", ".join(INTENTS) + "\n"
    "Respond with ONLY a JSON object with these exact fields:\n"
    '  - intent: the single best label\n'
    '  - confidence: float 0.0-1.0\n'
    '  - situation: 1-2 sentence description of what is happening\n'
    '  - computer_action: what the computer is doing in one phrase\n'
    '  - notable_phrase: the most characteristic computer phrase from this exchange\n'
    "No markdown. No explanation. Only the JSON object."
)

MODEL = "vercel:minimax/minimax-m2.7"
TOKEN = os.environ["ZO_CLIENT_IDENTITY_TOKEN"]

def parse_llm_output(raw: str) -> dict | None:
    """Parse LLM JSON response with multiple fallback strategies."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                cleaned = p
                break
    
    # Extract JSON object using regex as last resort
    if not cleaned.startswith("{"):
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            cleaned = m.group(0)
    
    try:
        parsed = json.loads(cleaned)
    except Exception:
        return None
    
    # Map various key names to canonical fields
    return {
        "intent": parsed.get("intent") or parsed.get("classification") or parsed.get("category") or "other",
        "confidence": float(parsed.get("confidence") or parsed.get("score") or 0.0),
        "situation": parsed.get("situation") or "",
        "computer_action": parsed.get("computer_action") or parsed.get("action") or "",
        "notable_phrase": parsed.get("notable_phrase") or parsed.get("notable") or "",
    }

def classify(cr: str, hq: str, series: str, episode: str) -> dict:
    prompt = (
        f"{SYSTEM}\n\n"
        f"Series: {series}\nEpisode: {episode}\n"
        f"Computer responses: \"{cr[:400]}\"\n"
        f"Human queries: \"{hq[:300]}\"\n\n"
        'Respond with ONLY a JSON object.'
    )
    payload = json.dumps({"input": prompt, "model_name": MODEL}).encode()
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(
        "https://api.zo.computer/zo/ask",
        data=payload,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
    raw = result.get("output", "")
    parsed = parse_llm_output(raw)
    if parsed:
        return parsed
    # Fallback: extract intent via regex from raw text
    intent_found = next((i for i in INTENTS if i in raw.lower()), "other")
    return {
        "intent": intent_found,
        "confidence": 0.0,
        "situation": "",
        "computer_action": "",
        "notable_phrase": "",
    }

def main():
    start = time.time()
    base = Path(__file__).parent.parent
    data = json.loads((base / "data" / "enriched.json").read_text())
    print(f"Loaded {len(data)} enriched conversations")

    for i, conv in enumerate(data):
        turns = conv.get("turns", [])
        cr = turns[0].get("computer_response", "") if turns else ""
        hq = turns[0].get("human_query", "") if turns else ""

        result = classify(cr, hq, conv.get("series", ""), conv.get("episode", ""))
        conv["intent"] = result["intent"]
        conv["intent_confidence"] = round(result["confidence"], 2)
        conv["situation"] = result["situation"]
        conv["computer_action"] = result["computer_action"]
        conv["notable_phrase"] = result["notable_phrase"]

        elapsed_total = time.time() - start
        rate = elapsed_total / (i + 1)
        remaining = rate * (len(data) - i - 1)
        print(f"  {i+1}/{len(data)} | {rate:.1f}s/call | ~{remaining/60:.0f}min | last=intent={result['intent']}")

    (base / "data" / "classified.json").write_text(json.dumps(data, indent=2))
    print(f"\nWrote {len(data)} classified -> data/classified.json")

    # Fine-tune JSONL
    ft_records = []
    for conv in data:
        for turn in conv.get("turns", []):
            hq = turn.get("human_query", "").strip()
            cr = turn.get("computer_response", "").strip()
            if hq and cr:
                ft_records.append(json.dumps({
                    "messages": [
                        {"role": "user", "content": hq},
                        {"role": "assistant", "content": cr},
                    ],
                    "intent": conv.get("intent", "other"),
                    "situation": conv.get("situation", ""),
                }))
    (base / "data" / "fine_tune.jsonl").write_text("\n".join(ft_records))
    print(f"Wrote {len(ft_records)} fine-tune records -> data/fine_tune.jsonl")

    intents = Counter(c.get("intent") for c in data)
    print("\nIntent distribution:")
    for intent, cnt in intents.most_common():
        print(f"  {intent}: {cnt} ({100*cnt/len(data):.1f}%)")

if __name__ == "__main__":
    main()
