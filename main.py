"""Main FastAPI application."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

import database as db
import flashcard_logic as fc
from models import LoginRequest, ProgressUpdate, FlashcardRating


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.ensure_indexes()
    yield
    await db.close_client()


app = FastAPI(lifespan=lifespan)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def get_chapter_words(chapter: int) -> list[dict]:
    doc = await db.get_db().chapters.find_one({"_id": chapter})
    if not doc:
        raise HTTPException(404, f"Chapter {chapter} not found")
    return doc["words"]


async def get_total_chapters() -> int:
    return await db.get_db().chapters.count_documents({})


# ── Info / Login ──────────────────────────────────────────────────────────────

@app.get("/api/info")
async def get_info():
    total = await get_total_chapters()
    return {"total_chapters": total, "words_per_chapter": 25}


@app.post("/api/login")
async def login(req: LoginRequest):
    username = req.username.strip().lower()
    if not username or len(username) > 30:
        raise HTTPException(400, "Invalid username")
    await db.get_db().users.update_one(
        {"_id": username},
        {"$setOnInsert": {"_id": username, "created_at": db.now()}},
        upsert=True,
    )
    return {"username": username}


# ── Words ─────────────────────────────────────────────────────────────────────

@app.get("/api/words/{chapter}")
async def get_words(chapter: int):
    words = await get_chapter_words(chapter)
    return {"chapter": chapter, "words": words}


# ── Progress (used by mcq, type, survival, speed) ────────────────────────────

@app.get("/api/progress/{username}")
async def get_progress(username: str):
    """Return progress broken down by chapter AND mode.

    Shape:
      {
        "1": {
          "all":      {correct, wrong, total, score, best_score},
          "mcq":      {correct, wrong, total, score},
          "type":     {...},
          "flashcard":{...},
          "survival": {best_score, ...},
          "speed":    {best_score, ...}
        },
        ...
      }
    """
    username = username.strip().lower()
    cursor = db.get_db().progress.find({"username": username})
    out: dict[str, dict] = {}

    async for row in cursor:
        ch = str(row["chapter"])
        mode = row.get("mode", "mcq")

        correct = row.get("correct", 0)
        wrong = row.get("wrong", 0)
        total = correct + wrong
        score = round(correct / total * 100) if total else 0
        best = row.get("best_score") or 0

        if ch not in out:
            out[ch] = {"all": {"correct": 0, "wrong": 0, "total": 0, "score": 0, "best_score": 0}}

        # Per-mode entry
        out[ch][mode] = {
            "correct": correct,
            "wrong": wrong,
            "total": total,
            "score": score,
            "best_score": best,
        }

        # Aggregate "all"
        all_ = out[ch]["all"]
        all_["correct"] += correct
        all_["wrong"] += wrong
        all_["total"] = all_["correct"] + all_["wrong"]
        all_["score"] = round(all_["correct"] / all_["total"] * 100) if all_["total"] else 0
        all_["best_score"] = max(all_["best_score"], best)

    return out


@app.post("/api/progress")
async def save_progress(data: ProgressUpdate):
    username = data.username.strip().lower()
    total_chapters = await get_total_chapters()
    if data.chapter > total_chapters:
        raise HTTPException(400, "Invalid chapter")

    key = f"{username}:{data.chapter}:{data.mode}"
    update = {
        "$inc": {"correct": data.correct, "wrong": data.wrong},
        "$set": {
            "username": username,
            "chapter": data.chapter,
            "mode": data.mode,
            "last_played": db.now(),
        },
    }
    if data.score is not None:
        # For survival/speed: track best score
        update["$max"] = {"best_score": data.score}

    await db.get_db().progress.update_one({"_id": key}, update, upsert=True)
    return {"ok": True}


# ── Leaderboard ───────────────────────────────────────────────────────────────

@app.get("/api/leaderboard/{chapter}")
async def leaderboard(chapter: int, mode: str = "mcq"):
    """Top 10 scores for a chapter+mode."""
    cursor = db.get_db().progress.find(
        {"chapter": chapter, "mode": mode}
    )
    rows = []
    async for r in cursor:
        correct = r.get("correct", 0)
        wrong = r.get("wrong", 0)
        total = correct + wrong
        if total == 0 and not r.get("best_score"):
            continue
        score = round(correct / total * 100) if total else 0
        rows.append({
            "username": r["username"],
            "correct": correct,
            "wrong": wrong,
            "score": score,
            "best_score": r.get("best_score", 0),
        })

    # Sort: for survival/speed use best_score, else accuracy
    if mode in ("survival", "speed"):
        rows.sort(key=lambda x: (-x["best_score"], -x["correct"]))
    else:
        rows.sort(key=lambda x: (-x["score"], -x["correct"]))
    return rows[:10]


# ── Flashcards (spaced repetition) ────────────────────────────────────────────

@app.get("/api/flashcards/{username}/{chapter}")
async def get_flashcards(username: str, chapter: int):
    """Get the chapter words ordered by ease (lowest first)."""
    username = username.strip().lower()
    words = await get_chapter_words(chapter)

    # Fetch existing ease values for this user+chapter
    cursor = db.get_db().flashcards.find({"username": username, "chapter": chapter})
    ease_map: dict[int, int] = {}
    async for row in cursor:
        ease_map[row["word_idx"]] = row.get("ease", 2)

    enriched = []
    for idx, w in enumerate(words):
        enriched.append({
            "word_idx": idx,
            "swedish": w["swedish"],
            "english": w["english"],
            "ease": ease_map.get(idx, 2),
        })
    # Sort: ease asc (struggling first), unseen (ease=2) in middle, easy (3) last
    enriched.sort(key=lambda x: x["ease"])
    return {"chapter": chapter, "cards": enriched}


@app.post("/api/flashcards/rate")
async def rate_flashcard(rating: FlashcardRating):
    username = rating.username.strip().lower()
    key = f"{username}:{rating.chapter}:{rating.word_idx}"

    # Get current ease
    existing = await db.get_db().flashcards.find_one({"_id": key})
    current_ease = existing.get("ease", 2) if existing else 2
    new_ease = fc.update_ease(current_ease, rating.rating)

    await db.get_db().flashcards.update_one(
        {"_id": key},
        {
            "$set": {
                "username": username,
                "chapter": rating.chapter,
                "word_idx": rating.word_idx,
                "ease": new_ease,
                "last_seen": db.now(),
            },
            "$inc": {"review_count": 1},
        },
        upsert=True,
    )
    return {"ease": new_ease, "requeue": fc.should_requeue(rating.rating)}


# ── Static files (must be last) ───────────────────────────────────────────────

app.mount("/", StaticFiles(directory="static", html=True), name="static")