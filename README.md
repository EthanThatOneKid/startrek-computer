# Star Trek Computer

> A study on language as an effective interface — using examples from Star Trek of users interacting with a computer verbally.

The goal is to understand what makes the Star Trek computer's language so precise, concise, and effective — then apply those patterns to real-world interfaces.

## Dataset

**730 deduplicated conversations** across 8 Star Trek series, extracted from episode transcripts via [`varenc/star_trek_transcript_search`](https://github.com/varenc/star_trek_transcript_search).

| Series | Conversations |
|---|---|
| Star Trek: The Next Generation | 238 |
| Star Trek: Voyager | 216 |
| Star Trek: Deep Space Nine | 137 |
| Star Trek: Discovery | 50 |
| Star Trek: The Original Series | 38 |
| Star Trek Films | 25 |
| Star Trek: Enterprise | 13 |
| Star Trek: The Animated Series | 13 |

## Intent Taxonomy

Each conversation is classified by the computer's primary function:

| Intent | Count | Description |
|---|---|---|
| `system_control` | 177 | Run programs, diagnostics, power management |
| `information_retrieval` | 140 | Locate people/objects, status queries, definitions |
| `warning_alert` | 90 | Danger warnings, imminent threats, anomalies |
| `security` | 43 | Access control, authorization, seals |
| `holodeck` | 42 | Holodeck programs and characters |
| `environmental` | 31 | Lighting, doors, gravity, atmosphere |
| `medical` | 27 | EMH, sickbay, patient records |
| `navigation` | 16 | Course, heading, warp, ETA |

164 remain `unknown` — flagged for LLM-assisted review.

## Zo Persona Mapping

If you want to turn this corpus into a Zo persona, start with the TNG voice and keep the role strictly operational.

- Use terse status language: `Affirmative.`, `Negative.`, `Confirmed.`, `Accessing.`, `Working.`
- Ask only for missing parameters: `Please specify.`
- Refuse or defer plainly: `That information is not available.`, `Unable to comply.`
- Keep responses short, impersonal, and exact.
- Prefer warnings, retrieval, completion, and system-status phrasing over conversational filler.

See `enterprise-computer-zo-persona.md` for a reusable persona prompt and examples.

## Pipeline

```
raw transcripts
  │
  ▼
scripts/export_conversations.py
  │ Finds every COMPUTER: / COMPUTER VOICE: line,
  │ clusters by 8-line proximity gap
  │
  ▼ data/conversations.json
scripts/enrich.py
  │ Adds series/season, stardate, per-turn query/response pairs,
  │ human speakers, multi-turn flag
  │
  ▼ data/enriched.json
scripts/classify.py
  │ Keyword-first intent classifier (9 categories)
  │
  ▼ data/classified.json
scripts/dedupe.py
  │ Exact dedup → canonical dedup → boilerplate removal
  │ ("affirmative", "negative", "acknowledged", "unable to comply")
  │
  ▼ data/deduplicated.json (730 conversations)
scripts/analyze.py
  │ Generates stats.md with distribution analysis
```

## Quick Start

```bash
# Clone with submodules
git clone --recurse-submodules https://github.com/EthanThatOneKid/startrek-computer.git
cd startrek-computer

# Or if already cloned
git submodule update --init

# Run full pipeline
python -m scripts.run_pipeline

# Run individual steps
python -m scripts.export_conversations
python -m scripts.enrich
python -m scripts.classify
python -m scripts.dedupe
python -m scripts.analyze
```

## Data Format

```json
{
  "episode": "100113.txt",
  "series": "NextGen",
  "series_title": "Star Trek: The Next Generation",
  "season": 1,
  "episode_num": 113,
  "stardate": "41291.4",
  "is_multi_turn": false,
  "num_human_turns": 1,
  "num_computer_turns": 1,
  "intent": "information_retrieval",
  "computer_responses": ["Lieutenant Commander Data now located in Holodeck area 4J."],
  "human_queries": ["Ensign, can you help me find Commander Data?"],
  "query": "Ensign, can you help me find Commander Data?",
  "turns": [
    {
      "computer_response": "Lieutenant Commander Data now located in Holodeck area 4J.",
      "human_query": "Ensign, can you help me find Commander Data?",
      "human_query_context": "Ensign, can you help me find Commander Data? This way, sir.",
      "line_num": 447
    }
  ]
}
```

## Credits

- Transcript source: [`varenc/star_trek_transcript_search`](https://github.com/varenc/star_trek_transcript_search)
