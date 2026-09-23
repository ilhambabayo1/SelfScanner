# ============================================================
# SELF SCANNER - routers/shelf.py (catalog, covers, shelf)
# ============================================================
import os

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse

from .. import db
from ..services.embedding_service import service as emb

router = APIRouter(prefix="/api", tags=["shelf"])


@router.get("/health")
async def health():
    return {
        "status": "ok" if emb.ready else "loading",
        "books_indexed": emb.embeddings.shape[0] if emb.ready else 0,
        "neighbors_loaded": emb.neighbors is not None,
        "catalog_loaded": emb.catalog is not None,
    }


@router.get("/books/{idx}")
async def book_detail(idx: int):
    if not emb.ready:
        raise HTTPException(503, "Engine still loading")
    if idx < 0 or idx >= emb.embeddings.shape[0]:
        raise HTTPException(404, "Book index out of range")
    info = emb.book(idx)
    info["neighbors"] = [emb.book(i) for i in emb.neighbors_of(idx, k=5)]
    return info


@router.get("/covers/{filename}")
async def cover_image(filename: str):
    if not emb.catalog:
        raise HTTPException(503, "Catalog not loaded")
    safe = os.path.basename(filename)  # prevent path traversal
    path = os.path.join(emb.catalog.get("dataset_dir", ""), safe)
    if not os.path.exists(path):
        raise HTTPException(404, "Cover not found")
    return FileResponse(path, media_type="image/jpeg")


@router.post("/shelf/{book_key}")
async def shelf_add(
    book_key: str,
    status: str = "want-to-read",
    rating: int = None,
    x_device_id: str = Header("", alias="X-Device-Id"),
):
    device = (x_device_id or "").strip()[:255]
    if not device:
        raise HTTPException(400, "Missing X-Device-Id header")
    if status not in ("want-to-read", "reading", "completed"):
        raise HTTPException(400, "Invalid status")
    db.ensure_device(device)
    db.shelf_add(device, book_key, status, rating)
    return {"ok": True}


@router.get("/shelf")
async def shelf_list(x_device_id: str = Header("", alias="X-Device-Id")):
    device = (x_device_id or "").strip()[:255]
    if not device:
        raise HTTPException(400, "Missing X-Device-Id header")
    return {"items": db.shelf_list(device)}



@router.get("/background")
async def background_covers(n: int = 48):
    """Random cover filenames for the UI's scattered-book background."""
    import random

    if not emb.ready:
        return {"covers": []}
    paths = emb.class_map["image_path"].astype(str).tolist()
    k = min(max(n, 1), len(paths))
    picks = random.sample(range(len(paths)), k)
    return {"covers": [os.path.basename(paths[i]) for i in picks]}