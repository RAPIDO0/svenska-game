"""Integration tests for the API routes."""
import pytest

pytestmark = pytest.mark.asyncio


# ── Login ─────────────────────────────────────────────────────────────────────

async def test_login_creates_user(client, seeded_db):
    r = await client.post("/api/login", json={"username": "Alice"})
    assert r.status_code == 200
    assert r.json() == {"username": "alice"}  # lowercased


async def test_login_is_idempotent(client, seeded_db):
    await client.post("/api/login", json={"username": "bob"})
    r = await client.post("/api/login", json={"username": "bob"})
    assert r.status_code == 200


async def test_login_rejects_empty(client, seeded_db):
    r = await client.post("/api/login", json={"username": "   "})
    assert r.status_code == 400


async def test_login_rejects_too_long(client, seeded_db):
    r = await client.post("/api/login", json={"username": "x" * 31})
    # Pydantic returns 422 for validation, our handler returns 400
    assert r.status_code in (400, 422)


# ── Info ──────────────────────────────────────────────────────────────────────

async def test_info_returns_chapter_count(client, seeded_db):
    r = await client.get("/api/info")
    assert r.status_code == 200
    assert r.json()["total_chapters"] == 2


# ── Words ─────────────────────────────────────────────────────────────────────

async def test_get_words_returns_chapter(client, seeded_db):
    r = await client.get("/api/words/1")
    data = r.json()
    assert r.status_code == 200
    assert data["chapter"] == 1
    assert len(data["words"]) == 3
    assert data["words"][0] == {"swedish": "hund", "english": "dog"}


async def test_get_words_404_on_missing_chapter(client, seeded_db):
    r = await client.get("/api/words/99")
    assert r.status_code == 404


# ── Progress ──────────────────────────────────────────────────────────────────

async def test_save_progress_accumulates(client, seeded_db):
    payload = {"username": "alice", "chapter": 1, "mode": "mcq",
               "correct": 5, "wrong": 2}
    await client.post("/api/progress", json=payload)
    await client.post("/api/progress", json=payload)

    r = await client.get("/api/progress/alice")
    data = r.json()
    assert data["1"]["correct"] == 10
    assert data["1"]["wrong"] == 4
    # 10 / 14 ≈ 71%
    assert data["1"]["score"] == 71


async def test_save_progress_invalid_chapter(client, seeded_db):
    r = await client.post("/api/progress", json={
        "username": "alice", "chapter": 999, "mode": "mcq",
        "correct": 1, "wrong": 0,
    })
    assert r.status_code == 400


async def test_progress_aggregates_across_modes(client, seeded_db):
    """Different modes for same chapter should merge in dashboard view."""
    await client.post("/api/progress", json={
        "username": "alice", "chapter": 1, "mode": "mcq",
        "correct": 5, "wrong": 0,
    })
    await client.post("/api/progress", json={
        "username": "alice", "chapter": 1, "mode": "type",
        "correct": 3, "wrong": 2,
    })
    r = await client.get("/api/progress/alice")
    data = r.json()
    assert data["1"]["correct"] == 8
    assert data["1"]["wrong"] == 2


async def test_survival_best_score_tracked(client, seeded_db):
    """Survival mode should keep the maximum score across attempts."""
    await client.post("/api/progress", json={
        "username": "alice", "chapter": 1, "mode": "survival",
        "correct": 7, "wrong": 3, "score": 7,
    })
    await client.post("/api/progress", json={
        "username": "alice", "chapter": 1, "mode": "survival",
        "correct": 4, "wrong": 3, "score": 4,
    })
    r = await client.get("/api/progress/alice")
    assert r.json()["1"]["best_score"] == 7  # not overwritten


# ── Leaderboard ───────────────────────────────────────────────────────────────

async def test_leaderboard_orders_by_score(client, seeded_db):
    await client.post("/api/progress", json={
        "username": "alice", "chapter": 1, "mode": "mcq",
        "correct": 10, "wrong": 0,  # 100%
    })
    await client.post("/api/progress", json={
        "username": "bob", "chapter": 1, "mode": "mcq",
        "correct": 5, "wrong": 5,  # 50%
    })
    r = await client.get("/api/leaderboard/1?mode=mcq")
    rows = r.json()
    assert len(rows) == 2
    assert rows[0]["username"] == "alice"
    assert rows[0]["score"] == 100


async def test_leaderboard_survival_uses_best_score(client, seeded_db):
    await client.post("/api/progress", json={
        "username": "alice", "chapter": 1, "mode": "survival",
        "correct": 5, "wrong": 1, "score": 5,
    })
    await client.post("/api/progress", json={
        "username": "bob", "chapter": 1, "mode": "survival",
        "correct": 8, "wrong": 1, "score": 8,
    })
    r = await client.get("/api/leaderboard/1?mode=survival")
    rows = r.json()
    assert rows[0]["username"] == "bob"
    assert rows[0]["best_score"] == 8


# ── Flashcards ────────────────────────────────────────────────────────────────

async def test_flashcards_default_ease(client, seeded_db):
    """A new user gets all cards at ease=2."""
    r = await client.get("/api/flashcards/alice/1")
    cards = r.json()["cards"]
    assert len(cards) == 3
    assert all(c["ease"] == 2 for c in cards)


async def test_flashcards_rate_unknown_drops_ease(client, seeded_db):
    r = await client.post("/api/flashcards/rate", json={
        "username": "alice", "chapter": 1, "word_idx": 0, "rating": "unknown",
    })
    body = r.json()
    assert body["ease"] == 1
    assert body["requeue"] is True


async def test_flashcards_rate_easy_raises_ease(client, seeded_db):
    r = await client.post("/api/flashcards/rate", json={
        "username": "alice", "chapter": 1, "word_idx": 0, "rating": "easy",
    })
    body = r.json()
    assert body["ease"] == 3
    assert body["requeue"] is False


async def test_flashcards_sorted_by_ease(client, seeded_db):
    """Words rated 'unknown' should come first in the next session."""
    await client.post("/api/flashcards/rate", json={
        "username": "alice", "chapter": 1, "word_idx": 2, "rating": "unknown",
    })
    await client.post("/api/flashcards/rate", json={
        "username": "alice", "chapter": 1, "word_idx": 0, "rating": "easy",
    })
    r = await client.get("/api/flashcards/alice/1")
    cards = r.json()["cards"]
    # Word 2 is unknown (ease=1) → first
    # Word 1 is unseen   (ease=2) → middle
    # Word 0 is easy     (ease=3) → last
    assert cards[0]["word_idx"] == 2
    assert cards[-1]["word_idx"] == 0
