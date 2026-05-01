"""MongoDB connection and helper functions."""
import os
from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from dotenv import load_dotenv
load_dotenv()
# Default to a local Mongo for tests; override in production via env var
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("MONGO_DB_NAME", "svenska")

_client: Optional[AsyncIOMotorClient] = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URL)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    return get_client()[DB_NAME]


async def close_client():
    global _client
    if _client is not None:
        _client.close()
        _client = None


# ── Collections ──────────────────────────────────────────────────────────────
# users:        { _id: username, created_at }
# chapters:     { _id: chapter_int, words: [{swedish, english}, ...] }
# progress:     { _id: "{user}:{chapter}", username, chapter, mode, correct,
#                 wrong, best_score, last_played }
# flashcards:   { _id: "{user}:{chapter}:{idx}", username, chapter, word_idx,
#                 swedish, english, ease, review_count, last_seen }


async def ensure_indexes():
    db = get_db()
    await db.progress.create_index([("username", 1), ("chapter", 1), ("mode", 1)])
    await db.flashcards.create_index([("username", 1), ("chapter", 1)])


def now() -> datetime:
    return datetime.now(timezone.utc)
