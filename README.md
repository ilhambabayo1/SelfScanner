# Self Scanner

Point your camera at a book cover - get the title, author, 5 similar books, and a
reading shelf that **learns your taste**.

## What it does

- **Scan** - Gemini Vision reads the cover (title, author, themes, pace, mood) and
  Google Books enriches it; a ResNet50 embedding engine matches the cover against a
  6,232-book catalog and returns the 5 most similar books.
- **Taste engine** - rate books 1-5 stars; the app learns hidden preferences
  (pattern lifts for narrative pace, themes, mood, style) and shows **predicted
  ratings** for unread books before you read them.
- **Shelf** - want-to-read / reading / completed, per device, no accounts.
- **Web UI** - responsive single-page app with a scattered-book-covers background,
  served by the API itself.

## Layout

```
backend/
  app/            FastAPI app (routers: scanner, shelf, taste; services: gemini, embeddings)
  static/         the web UI (vanilla HTML/CSS/JS, no build step)
  scripts/        artifact builders (rebuild_artifacts, build_neighbors, build_catalog)
  tests/          validation gates (pytest)
  data/           local artifacts + SQLite db (gitignored - rebuild or copy separately)
ihifix_project.ipynb   the original modeling notebook (embeddings training)
```

## Quick start

```powershell
cd backend
python -m uvicorn app.main:app --reload --port 8000
# open http://127.0.0.1:8000/
```

1. Put your Gemini key in `backend/.env` as `GEMINI_API_KEY=AIza...`
   (free at aistudio.google.com/apikey; without it the app runs in mock mode)
2. Artifacts are not in git - rebuild them with `backend/scripts/rebuild_artifacts.py`
   (needs the Kaggle 6000-children-and-teen-book-covers dataset) or copy `backend/data/`
   from a machine that has them.
3. Run tests: `python -m pytest backend/tests/test_backend.py -v`

See `backend/README.md` for the full API reference.
