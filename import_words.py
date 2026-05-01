"""Import or update words from a CSV file into MongoDB.

Usage:
    python import_words.py path/to/words.csv

The CSV is expected to have rows of the form:
    Swedish,English,<swedish_word>,<english_translation>
    English,Swedish,<english_word>,<swedish_translation>

Only `Swedish->English` rows are kept. Words are deduplicated by Swedish text.
Each chapter contains CHAPTER_SIZE words (default 25).

This script is idempotent: running it again replaces all chapters with the
new content. User progress is preserved (it lives in a separate collection).
"""
import asyncio
import math
import sys
from pathlib import Path

import pandas as pd

import database as db

CHAPTER_SIZE = 25


def parse_csv(csv_path: Path) -> list[dict]:
    """Parse the bilingual CSV and return Swedish->English word pairs."""
    df = pd.read_csv(csv_path, header=None)
    df.columns = ["from_lang", "to_lang", "word", "translation"]

    swe_eng = (
        df[df["from_lang"] == "Swedish"][["word", "translation"]]
        .drop_duplicates(subset="word")
        .reset_index(drop=True)
    )
    swe_eng.columns = ["swedish", "english"]
    return swe_eng.to_dict("records")


def split_chapters(words: list[dict], size: int = CHAPTER_SIZE) -> dict[int, list[dict]]:
    """Split a flat list of words into chapter-sized groups."""
    n_chapters = math.ceil(len(words) / size)
    chapters = {}
    for i in range(n_chapters):
        start = i * size
        end = min(start + size, len(words))
        chapters[i + 1] = words[start:end]
    return chapters


async def import_to_mongo(csv_path: Path) -> dict:
    """Read CSV and upsert chapter docs in MongoDB. Returns stats."""
    words = parse_csv(csv_path)
    chapters = split_chapters(words)

    chapters_col = db.get_db().chapters

    # Replace each chapter document
    for chapter_num, chapter_words in chapters.items():
        await chapters_col.replace_one(
            {"_id": chapter_num},
            {"_id": chapter_num, "words": chapter_words},
            upsert=True,
        )

    # Remove obsolete chapters (in case the new CSV is shorter)
    await chapters_col.delete_many({"_id": {"$gt": len(chapters)}})

    return {
        "total_words": len(words),
        "total_chapters": len(chapters),
        "last_chapter_size": len(chapters[len(chapters)]) if chapters else 0,
    }


async def main():
    if len(sys.argv) < 2:
        print("Usage: python import_words.py <csv_path>")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        sys.exit(1)

    print(f"Importing from {csv_path}…")
    stats = await import_to_mongo(csv_path)
    print(f"✓ Imported {stats['total_words']} words into "
          f"{stats['total_chapters']} chapters")
    print(f"  (last chapter has {stats['last_chapter_size']} words)")

    await db.close_client()


if __name__ == "__main__":
    asyncio.run(main())
