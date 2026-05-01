"""Simplified spaced-repetition logic for flashcards.

We use a 3-state ease score (1, 2, 3) instead of SM-2's continuous one
because the user only has 3 buttons. Words with lower ease are picked first.

Algorithm for picking the next card in a session:
- All cards start with ease=2.
- 'unknown' rating  → ease drops to 1, requeue immediately.
- 'hard'    rating  → ease stays the same.
- 'easy'    rating  → ease increases (capped at 3).
- Within a session, the queue is sorted by ease (lowest first).
"""
from typing import Literal

Rating = Literal["easy", "hard", "unknown"]


def update_ease(current_ease: int, rating: Rating) -> int:
    """Return the new ease value after a rating."""
    if rating == "unknown":
        return 1
    if rating == "hard":
        return max(1, current_ease)
    if rating == "easy":
        return min(3, current_ease + 1)
    raise ValueError(f"Unknown rating: {rating}")


def should_requeue(rating: Rating) -> bool:
    """Whether to put the card back in the same session's queue."""
    return rating == "unknown"


def session_score(easy_count: int, hard_count: int, unknown_count: int) -> int:
    """Compute a 0-100 score for a flashcard session."""
    total = easy_count + hard_count + unknown_count
    if total == 0:
        return 0
    points = easy_count * 1.0 + hard_count * 0.5 + unknown_count * 0.0
    return round(points / total * 100)
