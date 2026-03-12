from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Bullet:
    bullet_id: str
    text: str
    paragraph_index: int
    section_title: str
    role_title: str


@dataclass
class Role:
    title: str
    bullets: List[Bullet] = field(default_factory=list)


@dataclass
class Section:
    title: str
    roles: List[Role] = field(default_factory=list)


@dataclass
class ResumeData:
    sections: List[Section]
    bullet_index: Dict[str, Bullet]
    low_confidence: bool = False


@dataclass
class PhraseMatch:
    phrase: str
    match_type: str
    similarity: float
    evidence_bullet_id: Optional[str]
    evidence_text: Optional[str]


@dataclass
class RewriteSuggestion:
    bullet_id: str
    phrase: str
    original_text: str
    suggestion_text: str
