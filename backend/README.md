# Self Scanner - Backend API

Hybrid book scanner: **Gemini Vision** (free-tier identification) + **ResNet50 embeddings**
from your notebook (similarity recommendations).

## Setup (already done on this machine)

1. Artifacts rebuilt locally in `data/artifacts/`:
   - `cover_embedding.npy` (6232 x 2048, L2-normalized)
   - `class_map.csv` (6232 books)
   - `book_cover_model.keras` (ResNet50 embedding model)
   - `neighbors.json` (top-10 similar books for every book)
   - `catalog.json` (UI-facing book list)
2. Tests: `python -m pytest backend/tests/test_backend.py -v`  (5 passed)

## Run the server

```powershell
cd backend
python -m uvicorn app.main:app --port 8000
```

Interactive API docs: http://localhost:8000/docs

## Gemini Vision: live vs mock

By default the API runs in **mock mode** (no key needed). To go live:

```powershell
$env:GEMINI_API_KEY = "AIza..."   # from https://aistudio.google.com/apikey
python -m uvicorn app.main:app --port 8000
```

Optionally pin a model with `GEMINI_MODEL` (default `gemini-flash-latest`),
or force offline mode with `GEMINI_MOCK=1`.

Prefer a file? Put `GEMINI_API_KEY=your-key` in `backend/.env` - it is
loaded automatically when the server starts (a real environment
variable always wins).

## Key endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/scan` | Upload cover photo -> identification + 5 similar books |
| GET | `/api/health` | Engine readiness |
| GET | `/api/books/{idx}` | Book detail + neighbors |
| GET | `/api/books/{idx}/neighbors` | Similar books |
| GET | `/api/covers/{filename}` | Serve a catalog cover image |
| POST | `/api/shelf/{book_key}` | Add/update reading status (X-Device-Id header) |
| GET | `/api/shelf` | List shelf for device |

Example scan (PowerShell):

```powershell
curl -X POST http://localhost:8000/api/scan `
  -H "X-Device-Id: my-device-1" `
  -F "file=@some_cover.jpg"
```

## Scripts (backend/scripts/)

- `rebuild_artifacts.py` - rebuild embeddings from the Kaggle dataset (~15 min CPU)
- `build_neighbors.py` - recompute top-10 neighbor lists
- `build_catalog.py` - rebuild catalog.json (`--enrich` adds Google Books metadata)

## Web UI

A responsive single-page UI ships with the backend - start the server and open
http://127.0.0.1:8000/ - scan covers by photo/drag-drop, see the identified
book + 5 similar covers (ResNet50 embeddings), and build your reading shelf.
The scattered-book background is drawn from the catalog itself.

## Taste engine (pattern recognition + predicted ratings)

- **Rate** a scanned book (1-5 stars) - the UI shows stars after every scan, or:
  `POST /api/rate/{book_key}?rating=5`
- **GET /api/profile** returns the learned profile:
  - `patterns` - hidden preferences detected from your ratings (mood, narrative
    pace, themes, cover style), e.g. rating slow-burn books higher than chance
  - `predictions` - predicted star ratings for unread books, from a taste
    vector (embedding centroid weighted by your ratings) + attribute lifts,
    each with a "why" (nearest liked book)
- Confidence grows with the number of ratings; nothing is sent anywhere -
  all personalization is per-device and computed locally.
