# Svenska — Swedish Vocabulary Game (v2)

5 game modes, MongoDB backend, leaderboards, spaced repetition.

## Game Modes

- **Multiple choice** — pick the right translation from 4 options
- **Typing** — type the translation
- **Flashcards** — spaced-repetition self-rating (Easy/Hard/Don't know)
- **Survival** — 3 lives, see how many words you can get before dying
- **Speed (60s)** — answer as many words as possible in 60 seconds

## Project Structure

```
svenska_app/
├── main.py             ← FastAPI routes
├── database.py         ← MongoDB connection
├── models.py           ← Pydantic models
├── flashcard_logic.py  ← Spaced-repetition logic
├── import_words.py     ← CSV → MongoDB script
├── requirements.txt
├── requirements-test.txt
├── pytest.ini
├── render.yaml
├── .python-version
├── tests/
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_flashcard.py
│   └── test_import.py
└── static/
    └── index.html
```

---

## Local Setup

### 1. Install MongoDB

**Option A — Local Mongo (easiest for dev):**
```bash
# Ubuntu/WSL
sudo apt update && sudo apt install -y mongodb
sudo systemctl start mongodb     # or: mongod &
```

**Option B — MongoDB Atlas (free cloud):**
- Sign up at https://www.mongodb.com/cloud/atlas
- Create a free M0 cluster
- Get the connection string (looks like `mongodb+srv://...`)

### 2. Set up the project

```bash
cd svenska_app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Set the Mongo URL

```bash
# Local Mongo (default)
export MONGO_URL="mongodb://localhost:27017"

# Or Atlas:
export MONGO_URL="mongodb+srv://user:pass@cluster.mongodb.net"
```

### 4. Import your words

```bash
python import_words.py path/to/your_words.csv
```

This reads the CSV, splits into chapters of 25, and writes them to MongoDB. **Re-run any time you update the CSV** — your users' progress is preserved.

### 5. Run

```bash
uvicorn main:app --reload
# → http://localhost:8000
```

---

## Running Tests

```bash
pip install -r requirements-test.txt
pytest
```

Tests use `mongomock-motor` (an in-memory mock), so you don't need a real Mongo running. Should print `33 passed` in ~1.5s.

---

## Deploying to Render

### 1. Set up MongoDB Atlas (if not already)

Render's free Postgres expires after 90 days, so for free persistence use Atlas. Get your connection string.

### 2. Push to GitHub

```bash
git add .
git commit -m "v2: mongodb + new modes"
git push
```

### 3. Render dashboard

- Your existing service should auto-redeploy.
- Go to the service → **Environment** tab → add:
  - `MONGO_URL` = your Atlas connection string
  - `MONGO_DB_NAME` = `svenska`

### 4. Import words on Render

The first time, you need to import words from your CSV. Easiest way: **run `import_words.py` locally pointing at your Atlas URL.**

```bash
export MONGO_URL="mongodb+srv://..."
python import_words.py words.csv
```

This populates Atlas, and your deployed app reads from the same DB.

---

## Updating the word list

Just edit your CSV and re-run:

```bash
python import_words.py new_words.csv
```

The script:
- Replaces all chapter documents with the new content
- Removes any chapters that no longer exist
- **Leaves user progress untouched** (it's in a different collection)

If a chapter changes, old user stats for that chapter still apply (since they're tracked per chapter number, not per word).

---

## Architecture notes

**Collections in MongoDB:**

| Collection  | Document shape                                              |
|-------------|-------------------------------------------------------------|
| `users`     | `{_id: username, created_at}`                               |
| `chapters`  | `{_id: chapter_int, words: [{swedish, english}, ...]}`      |
| `progress`  | `{_id: "user:ch:mode", correct, wrong, best_score, ...}`    |
| `flashcards`| `{_id: "user:ch:idx", ease, review_count, last_seen}`       |

**Why one progress doc per (user, chapter, mode):**
This lets us track separate stats for each game mode while keeping queries simple. The dashboard aggregates across modes, the leaderboard filters by mode.

**Spaced repetition:** Simplified SM-2 with 3 ease levels (1–3). Words you mark "Don't know" drop to ease 1 and come back at the end of the same session. Words you mark "Easy" rise to ease 3 and come last next time.
