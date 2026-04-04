from typing import List, Optional
from pydantic import BaseModel, Field

class SceneContext(BaseModel):
    series: str
    series_title: str
    season: int
    episode: str
    episode_num: int
    stardate: Optional[str] = None
    start_line: int
    end_line: int

class SpeechAct(BaseModel):
    speaker: Optional[str]
    text: str
    line_num: int
    is_computer: bool
    raw: str

class Classification(BaseModel):
    intent: str
    confidence: float
    situation: str
    computer_action: str
    notable_phrase: Optional[str] = None

class Candidate(BaseModel):
    """The computer's response and its associated classification."""
    index: int
    content: str
    classification: Classification

class GroundingSupport(BaseModel):
    """Evidence for a specific classification or computer action."""
    grounding_chunk_indices: List[int] # Indices in Interaction.transcript

class GroundingMetadata(BaseModel):
    """Contextual metadata that grounds the interaction in the transcript."""
    grounding_supports: List[GroundingSupport]

class Interaction(BaseModel):
    id: str # Stable hash of the transcript lines
    context: SceneContext
    transcript: List[SpeechAct]
    candidates: List[Candidate]
    grounding_metadata: GroundingMetadata
    is_multi_turn: bool
    num_human_turns: int
    num_computer_turns: int

class Dataset(BaseModel):
    interactions: List[Interaction]
