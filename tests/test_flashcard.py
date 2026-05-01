"""Unit tests for the flashcard ease/scoring logic."""
import pytest

from flashcard_logic import update_ease, should_requeue, session_score


# ── update_ease ───────────────────────────────────────────────────────────────

def test_unknown_drops_to_one():
    assert update_ease(2, "unknown") == 1
    assert update_ease(3, "unknown") == 1


def test_hard_keeps_ease():
    assert update_ease(2, "hard") == 2
    assert update_ease(3, "hard") == 3


def test_easy_increases_ease_capped_at_three():
    assert update_ease(1, "easy") == 2
    assert update_ease(2, "easy") == 3
    assert update_ease(3, "easy") == 3  # capped


def test_unknown_rating_raises():
    with pytest.raises(ValueError):
        update_ease(2, "what")  # type: ignore


# ── should_requeue ────────────────────────────────────────────────────────────

def test_only_unknown_requeues():
    assert should_requeue("unknown") is True
    assert should_requeue("hard") is False
    assert should_requeue("easy") is False


# ── session_score ─────────────────────────────────────────────────────────────

def test_score_all_easy_is_100():
    assert session_score(easy_count=10, hard_count=0, unknown_count=0) == 100


def test_score_all_unknown_is_0():
    assert session_score(easy_count=0, hard_count=0, unknown_count=5) == 0


def test_score_handles_zero_total():
    assert session_score(0, 0, 0) == 0


def test_score_mixed():
    # 5 easy (5pt), 5 hard (2.5pt), 0 unknown → 7.5/10 = 75%
    assert session_score(easy_count=5, hard_count=5, unknown_count=0) == 75
