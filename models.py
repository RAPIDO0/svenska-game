"""Pydantic request/response models."""
from typing import Literal
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=30)


class ProgressUpdate(BaseModel):
    username: str
    chapter: int = Field(ge=1)
    mode: Literal["mcq", "type", "survival", "speed", "flashcard"] = "mcq"
    correct: int = Field(ge=0)
    wrong: int = Field(ge=0)
    # Optional best-score (used by survival/speed modes)
    score: int | None = None


class FlashcardRating(BaseModel):
    """User rates how well they knew a flashcard."""
    username: str
    chapter: int
    word_idx: int
    rating: Literal["easy", "hard", "unknown"]
