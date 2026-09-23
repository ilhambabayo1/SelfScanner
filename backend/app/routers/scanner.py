# ============================================================
# SELF SCANNER - routers/scanner.py (the hybrid endpoint)
# POST /api/scan: photo -> Gemini identify (Track A)
#                       + embedding similarity (Track B)
# ============================================================
from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

from .. import db
from ..config import DAILY_SCAN_LIMIT
from ..services.vision import identify, active_provider
from ..services.embedding_service import service as emb
from ..services import google_books

router = APIRouter(prefix="/api", tags=["scanner"])


@router.post("/scan")
async def scan(
    file: UploadFile = File(...),
    device_id: str = Form(""),
    x_device_id: str = Header("", alias="X-Device-Id"),
):
    device = (x_device_id or device_id or "").strip()[:255]
    if not device:
        raise HTTPException(400, "Missing device_id (form field or X-Device-Id header)")

    if not emb.ready:
        raise HTTPException(503, "Embedding engine still loading, retry shortly")

    if not db.check_rate_limit(device, DAILY_SCAN_LIMIT):
        raise HTTPException(429, f"Daily scan limit ({DAILY_SCAN_LIMIT}) reached")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(400, "Empty upload")

    # --- Track A: Gemini Vision identification ---
    try:
        identified = identify(image_bytes)
    except Exception as e:  # noqa: BLE001 - degrade gracefully
        identified = {"is_book_cover": False, "title": "", "confidence": 0.0,
                      "error": f"identification failed: {e}"}

    # --- Track B: embedding similarity ---
    from io import BytesIO
    from PIL import Image

    try:
        pil_img = Image.open(BytesIO(image_bytes))
    except Exception:
        raise HTTPException(400, "Uploaded file is not a readable image")

    matches = emb.search(pil_img, k=5)
    results = []
    for m in matches:
        book = emb.book(m["idx"])
        book["similarity"] = round(m["similarity"], 4)
        results.append(book)

    # --- Enrich the best guess with Google Books metadata ---
    title = (identified.get("title") or "").strip()
    author = (identified.get("author") or "").strip()
    enriched = google_books.lookup(title, author) if title else {}

    db.ensure_device(device)
    db.record_scan(
        device,
        DAILY_SCAN_LIMIT,
        title=title or results[0]["title"] if results else title,
        author=author,
        isbn=identified.get("isbn", ""),
        match_idx=results[0]["idx"] if results else None,
        similarity=results[0]["similarity"] if results else None,
        source=f"{active_provider()}+embeddings",
        confidence=identified.get("confidence"),
        metadata={"age_band": identified.get("age_band"),
                  "mood": identified.get("mood"),
                  "style": identified.get("cover_style")},
    )

    return {
        "identified": identified,
        "identification_provider": active_provider(),
        "enriched": enriched,
        "similar_books": results,
    }
