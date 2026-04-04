#!/usr/bin/env python3
"""
classify_llm.py — Classify ALL conversations via OpenRouter LLM.
Each conversation gets: intent, confidence, situation, computer_action, notable_phrase.
Output: classified.json + fine_tune.jsonl
"""
import json, time, os, re
from collections import Counter
from pathlib import Path
import urllib.request
import urllib.error

# Manual .env loader
def load_dotenv():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

load_dotenv()

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

MODEL = "google/gemini-2.0-flash-001"
API_KEY = os.environ.get("OPENROUTER_API_KEY")

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
    if not API_KEY:
        raise ValueError("OPENROUTER_API_KEY not found in environment or .env")

    user_prompt = (
        f"Series: {series}\nEpisode: {episode}\n"
        f"Computer responses: \"{cr[:400]}\"\n"
        f"Human queries: \"{hq[:300]}\"\n\n"
        'Respond with ONLY a JSON object.'
    )
    
    payload_data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.0,
    }
    
    if "gemini" in MODEL.lower() or "gpt" in MODEL.lower():
        payload_data["response_format"] = {"type": "json_object"}

    payload = json.dumps(payload_data).encode()
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/EthanThatOneKid/startrek-computer",
        "X-Title": "Star Trek Computer Pipeline"
    }
    
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers=headers,
        method="POST",
    )
    
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        raw = result["choices"][0]["message"]["content"]
        parsed = parse_llm_output(raw)
        if parsed:
            return parsed
    except Exception as e:
        print(f"  Error calling API: {e}")
    
    return {
        "intent": "other",
        "confidence": 0.0,
        "situation": "",
        "computer_action": "",
        "notable_phrase": "",
    }

def main():
    start = time.time()
    base = Path(__file__).parent.parent
    data_path = base / "data" / "enriched.json"
    data = json.loads(data_path.read_text())
    print(f"Loaded {len(data)} enriched conversations")

    # Load existing classified data to resume/preserve
    classified_path = base / "data" / "classified.json"
    if classified_path.exists():
        try:
            old_data = json.loads(classified_path.read_text())
            # Map by episode + line_num or index
            # Simplest for now since we haven't filtered yet: index
            for i, old_conv in enumerate(old_data):
                if i < len(data):
                    # Check if it already has rich LLM fields
                    if old_conv.get("situation") and old_conv.get("intent_confidence", 0) > 0:
                        data[i] = old_conv
        except Exception as e:
            print(f"  Warning: could not resume from existing file: {e}")

    # Identify items needing classification
    needs_reclass = [i for i, c in enumerate(data) if not c.get("situation")]
    print(f"  Items needing LLM classification: {len(needs_reclass)}")

    for count, i in enumerate(needs_reclass):
        conv = data[i]
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
        rate = elapsed_total / (count + 1)
        remaining = rate * (len(needs_reclass) - count - 1)
        print(f"  {count+1}/{len(needs_reclass)} | {rate:.1f}s/call | ~{remaining/60:.0f}min | last=intent={result['intent']}")

        # Save checkpoint every 25 calls
        if (count + 1) % 25 == 0:
            classified_path.write_text(json.dumps(data, indent=2))

    classified_path.write_text(json.dumps(data, indent=2))
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
