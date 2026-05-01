"""Shared pytest fixtures."""
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Ensure project root is on sys.path so `import database`, `import main` work
sys.path.insert(0, str(Path(__file__).parent.parent))

# Use mongomock so tests don't need a real Mongo running
import mongomock_motor

import database
import main as main_module


@pytest.fixture(autouse=True)
def patch_mongo(monkeypatch):
    """Replace the real Mongo client with an in-memory mock for every test."""
    mock_client = mongomock_motor.AsyncMongoMockClient()
    monkeypatch.setattr(database, "_client", mock_client)
    monkeypatch.setattr(database, "get_client", lambda: mock_client)
    monkeypatch.setattr(database, "get_db", lambda: mock_client[database.DB_NAME])
    yield


@pytest_asyncio.fixture
async def client():
    """An async HTTP client for the FastAPI app."""
    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def seeded_db():
    """Insert two chapters of test words into the mock Mongo."""
    db = database.get_db()
    await db.chapters.replace_one(
        {"_id": 1},
        {"_id": 1, "words": [
            {"swedish": "hund", "english": "dog"},
            {"swedish": "katt", "english": "cat"},
            {"swedish": "bok", "english": "book"},
        ]},
        upsert=True,
    )
    await db.chapters.replace_one(
        {"_id": 2},
        {"_id": 2, "words": [
            {"swedish": "hus", "english": "house"},
            {"swedish": "bil", "english": "car"},
        ]},
        upsert=True,
    )
    yield db
