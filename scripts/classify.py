#!/usr/bin/env python3
"""
classify.py — Intent classification for computer conversations.
Keyword-first classifier; LLM fallback for UNKNOWN cases.
Run: python -m scripts.classify
"""
import json
import os
from enum import Enum
from pathlib import Path
from typing import Optional

# -------------------------------------------------------------------
# Intent definitions
# -------------------------------------------------------------------

class Intent(Enum):
    INFORMATION_RETRIEVAL = "information_retrieval"
    SYSTEM_CONTROL = "system_control"
    WARNING_ALERT = "warning_alert"
    ENVIRONMENTAL = "environmental"
    HOLODECK = "holodeck"
    MEDICAL = "medical"
    NAVIGATION = "navigation"
    SECURITY = "security"
    UNKNOWN = "unknown"


INTENT_PATTERNS = {
    Intent.INFORMATION_RETRIEVAL: [
        "what is", "what are", "where is", "where are",
        "who is", "who was", "who are", "tell me",
        "information", "locate", "location", "status of",
        "definition", "meaning", "identify", "recognize",
        "how many", "how much", "how long", "how far",
        "list", "catalog", "index", "record",
        "coordinates", "position", "current location",
    ],
    Intent.SYSTEM_CONTROL: [
        "run ", "run a", "execute", "initiate",
        "activate", "deactivate", "disable", "enable",
        "reset", "restart", "shutdown", "reboot",
        "diagnostic", "power", "offline", "online",
        "calibrate", "load", "unload", "eject",
        "begin", "end", "stop", "start",
    ],
    Intent.WARNING_ALERT: [
        "warning", "caution", "hazard", "alert",
        "emergency", "critical", "breach", "failure",
        "imminent", "danger", "incoming", "inbound",
        "decloaking", "anomaly", "fluctuation",
    ],
    Intent.ENVIRONMENTAL: [
        "temperature", "lights", "door", "force field",
        "gravity", "atmosphere", "air", "climate",
        "humidity", "ventilation", "environmental",
        "illumination", "darkness", "heat", "cold",
        "seal", "unseal", "open", "close",
    ],
    Intent.HOLODECK: [
        "holodeck", "holoprogram", "programme", "program",
        "simulation", "run program", "characters",
        "holo-novel", "holo-production",
    ],
    Intent.MEDICAL: [
        "medical", "bio", "genetic", "pharmaceutical",
        "hypospray", "sickbay", "EMH", "doctor",
        "health", "injury", "wound", "patient",
        "treatment", "therapy", "diagnosis",
    ],
    Intent.NAVIGATION: [
        "course", "heading", "warp", "impulse",
        "navigate", "plot", "destination", "ETA",
        "speed", "velocity", "trajectory", "bearing",
        "bearing", "intercept", "rendezvous",
    ],
    Intent.SECURITY: [
        "security", "lock", "unlock", "authorization",
        "access", "clearance", "code", "password",
        "permission", "restrict", "seal", "containment",
    ],
}


def classify(text: str) -> Intent:
    """Keyword-first intent classifier. Returns first matching intent."""
    text_lower = text.lower()
    for intent, keywords in INTENT_PATTERNS.items():
        if any(kw in text_lower for kw in keywords):
            return intent
    return Intent.UNKNOWN


def classify_computer_response(text: str) -> Intent:
    """Classify based on computer response text (more reliable than queries)."""
    return classify(text)


def classify_human_query(text: str) -> Intent:
    """Classify based on human query text."""
    return classify(text)


def classify_conversation(computer_texts: list[str], human_queries: list[str]) -> dict:
    """Classify a conversation by combining signals from computer responses and queries."""
    # Score each intent by frequency across all texts
    scores: dict[Intent, int] = {i: 0 for i in Intent}

    for text in computer_texts + human_queries:
        if not text:
            continue
        intent = classify(text)
        scores[intent] += 1

    # Multi-turn: weight intents seen in multiple exchanges
    # Winner = highest non-UNKNOWN score
    winner = Intent.UNKNOWN
    best = 0
    for intent, score in scores.items():
        if intent != Intent.UNKNOWN and score > best:
            best = score
            winner = intent

    return {
        "primary_intent": winner.value,
        "intent_scores": {i.value: s for i, s in scores.items()},
        "confidence": best / max(sum(scores.values()), 1),
    }


def llm_classify(texts: list[str]) -> Optional[dict]:
    """Fallback LLM classification for UNKNOWN conversations."""
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    system = (
        "You are a classifier. Given a Star Trek computer conversation, "
        "classify the computer's primary function into one of: "
        "information_retrieval, system_control, warning_alert, environmental, "
        "holodeck, medical, navigation, security. "
        "Respond with ONLY the intent name, nothing else."
    )
    user = "\n".join(f"Computer: {t}" for t in texts if t)

    # (LLM integration deferred — requires API key + client setup)
    return None


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

def main():
    import sys
    base_dir = Path(__file__).parent.parent

    conv_file = base_dir / "data" / "enriched.json"
    out_file = base_dir / "data" / "classified.json"

    if not conv_file.exists():
        print("ERROR: data/enriched.json not found. Run enrich.py first.")
        return

    conversations = json.loads(conv_file.read_text())
    print(f"Loaded {len(conversations)} enriched conversations")

    unknown_count = 0
    llm_flagged = []

    for i, conv in enumerate(conversations):
        computer_texts = conv.get("computer_responses", []) or conv.get("_raw_computer_texts", [])
        human_queries = conv.get("human_queries", [])

        result = classify_conversation(computer_texts, human_queries)

        conv["intent"] = result["primary_intent"]
        conv["intent_scores"] = result["intent_scores"]
        conv["confidence"] = round(result["confidence"], 3)

        if result["primary_intent"] == Intent.UNKNOWN.value:
            unknown_count += 1
            if len(computer_texts) >= 2:
                llm_flagged.append(conv["episode"])

        if (i + 1) % 200 == 0:
            print(f"  Processed {i + 1}/{len(conversations)}")

    out_file.write_text(json.dumps(conversations, indent=2))
    print(f"\nWrote {len(conversations)} classified conversations to {out_file}")
    print(f"  UNKNOWN: {unknown_count} ({100*unknown_count/len(conversations):.1f}%)")
    print(f"  Flagged for LLM review: {len(llm_flagged)}")


if __name__ == "__main__":
    main()
