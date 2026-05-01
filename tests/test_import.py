"""Tests for the CSV import script."""
import io
from pathlib import Path

import pytest

import database
from import_words import parse_csv, split_chapters, import_to_mongo


CSV_CONTENT = """Swedish,English,hund,dog
Swedish,English,katt,cat
English,Swedish,dog,hund
Swedish,English,bok,book
Swedish,English,hund,dog
"""


@pytest.fixture
def csv_file(tmp_path) -> Path:
    f = tmp_path / "words.csv"
    f.write_text(CSV_CONTENT, encoding="utf-8")
    return f


# ── Parsing ───────────────────────────────────────────────────────────────────

def test_parse_csv_keeps_only_swedish_to_english(csv_file):
    words = parse_csv(csv_file)
    assert len(words) == 3  # english→swedish row dropped, dup dropped
    swedish = [w["swedish"] for w in words]
    assert "hund" in swedish
    assert "dog" not in swedish


def test_parse_csv_dedupes(csv_file):
    words = parse_csv(csv_file)
    swedish = [w["swedish"] for w in words]
    assert swedish.count("hund") == 1


# ── Splitting ─────────────────────────────────────────────────────────────────

def test_split_chapters_sizes():
    words = [{"swedish": f"sv{i}", "english": f"en{i}"} for i in range(53)]
    chapters = split_chapters(words, size=25)
    assert len(chapters) == 3
    assert len(chapters[1]) == 25
    assert len(chapters[2]) == 25
    assert len(chapters[3]) == 3  # remainder


def test_split_chapters_empty():
    assert split_chapters([], size=25) == {}


def test_split_chapters_exact_fit():
    words = [{"swedish": f"sv{i}", "english": f"en{i}"} for i in range(50)]
    chapters = split_chapters(words, size=25)
    assert len(chapters) == 2
    assert len(chapters[2]) == 25


# ── Mongo import ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_import_writes_chapters(csv_file):
    stats = await import_to_mongo(csv_file)
    assert stats["total_words"] == 3
    assert stats["total_chapters"] == 1

    db = database.get_db()
    doc = await db.chapters.find_one({"_id": 1})
    assert doc is not None
    assert len(doc["words"]) == 3


@pytest.mark.asyncio
async def test_import_replaces_old_chapters(tmp_path):
    """Re-importing with fewer chapters should remove the old ones."""
    db = database.get_db()
    # Pre-seed with 5 chapters
    for i in range(1, 6):
        await db.chapters.insert_one({"_id": i, "words": [{"swedish": "x", "english": "y"}]})

    # Now import a tiny CSV (1 chapter)
    f = tmp_path / "small.csv"
    f.write_text("Swedish,English,hund,dog\n")
    stats = await import_to_mongo(f)

    assert stats["total_chapters"] == 1
    remaining = await db.chapters.count_documents({})
    assert remaining == 1
