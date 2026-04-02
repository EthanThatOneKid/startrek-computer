#!/usr/bin/env python3
"""
classify.py — Keyword-first intent classifier.
Fast, deterministic, no API calls needed.
Run: python -m scripts.classify
"""
import json
from enum import Enum
from pathlib import Path

# ------------------------------------------------------------------ #
# Intent definitions
# ------------------------------------------------------------------ #

class Intent(Enum):
    INFORMATION_RETRIEVAL = "information_retrieval"
    SYSTEM_CONTROL = "system_control"
    WARNING_ALERT = "warning_alert"
    ENVIRONMENTAL = "environmental"
    HOLODECK = "holodeck"
    MEDICAL = "medical"
    NAVIGATION = "navigation"
    SECURITY = "security"
    OTHER = "other"

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
        "diagnostic", "power ", "offline", "online",
        "calibrate", "load ", "unload", "eject",
        "begin", "end", "stop ", "start ",
    ],
    Intent.WARNING_ALERT: [
        "warning", "caution", "hazard", "alert",
        "emergency", "critical", "breach", "failure",
        "imminent", "danger", "incoming", "inbound",
        "decloaking", "anomaly", "fluctuation",
        "containment", "evacuate",
    ],
    Intent.ENVIRONMENTAL: [
        "temperature", "lights", "door", "force field",
        "gravity", "atmosphere", "air", "climate",
        "humidity", "ventilation", "environmental",
        "illumination", "darkness", "heat", "cold",
        "seal", "unseal",
    ],
    Intent.HOLODECK: [
        "holodeck", "holoprogram", "programme", "holo-program",
        "simulation", "run program", "characters",
        "holo-novel", "holo-production",
    ],
    Intent.MEDICAL: [
        "medical", "bio", "genetic", "pharmaceutical",
        "hypospray", "sickbay", "emh", "doctor",
        "health", "injury", "wound", "patient",
        "treatment", "therapy", "diagnosis",
    ],
    Intent.NAVIGATION: [
        "course", "heading", "warp", "impulse",
        "navigate", "plot ", "destination", "eta",
        "speed", "velocity", "trajectory", "bearing",
        "intercept", "rendezvous",
    ],
    Intent.SECURITY: [
        "security", "lock", "unlock", "authorization",
        "access", "clearance", "code", "password",
        "permission", "restrict", "containment",
    ],
}

# ------------------------------------------------------------------ #
# Classifier
# ------------------------------------------------------------------ #

def classify(text: str) -> Intent:
    """Keyword-first intent classifier."""
    text_lower = text.lower()
    for intent, keywords in INTENT_PATTERNS.items():
        if any(kw in text_lower for kw in keywords):
            return intent
    return Intent.OTHER

def classify_conversation(computer_texts: list[str], human_queries: list[str]) -> dict:
    """Classify by combining signals from computer responses and queries."""
    # Weight: computer response > human query
    scores: dict[Intent, float] = {i: 0.0 for i in Intent}
    
    for ct in computer_texts:
        intent = classify(ct)
        scores[intent] += 2.0
    
    for hq in human_queries:
        intent = classify(hq)
        scores[intent] += 1.0
    
    best_intent = max(scores, key=scores.get)
    best_score = scores[best_intent]
    confidence = min(best_score / 4.0, 1.0) if best_score > 0 else 0.0
    
    return {
        "intent": best_intent.value,
        "confidence": round(confidence, 2),
    }

# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #

def main():
    base = Path(__file__).parent.parent
    data = json.loads((base / "data" / "enriched.json").read_text())
    print(f"Loaded {len(data)} enriched conversations")

    unknown_count = 0
    for conv in data:
        computer_texts = conv.get("computer_responses", [])
        human_queries = conv.get("human_queries", [])
        
        result = classify_conversation(computer_texts, human_queries)
        conv["intent"] = result["intent"]
        conv["intent_confidence"] = result["confidence"]
        
        if result["intent"] == "other":
            unknown_count += 1

    (base / "data" / "classified.json").write_text(json.dumps(data, indent=2))
    print(f"Wrote {len(data)} classified -> data/classified.json")
    print(f"  UNKNOWN (other): {unknown_count} ({100*unknown_count/len(data):.1f}%)")

    from collections import Counter
    intents = Counter(c.get("intent") for c in data)
    print("\nIntent distribution:")
    for intent, cnt in intents.most_common():
        print(f"  {intent}: {cnt} ({100*cnt/len(data):.1f}%)")

if __name__ == "__main__":
    main()
