# ============================================================
# SELF SCANNER - routers/taste.py (pattern recognition API)
# ============================================================
from fastapi import APIRouter, Header, HTTPException, Query

from .. import db
from ..services.taste_service import service as taste

router = APIRouter(prefix="/api", tags=["taste"])


@router.post("/rate/{book_key}")
async def rate_book(
    book_key: str,
    rating: int = Query(..., ge=1, le=5),
    status: str = None,
    x_device_id: str = Header("", alias="X-Device-Id"),
):
    device = (x_device_id or "").strip()[:255]
    if not device:
        raise HTTPException(400, "Missing X-Device-Id header")
    db.ensure_device(device)
    db.rate_book(device, book_key.strip()[:255], rating, status)
    return {"ok": True}


@router.get("/profile")
async def profile(
    predictions: int = Query(6, ge=0, le=24),
    x_device_id: str = Header("", alias="X-Device-Id"),
):
    device = (x_device_id or "").strip()[:255]
    if not device:
        raise HTTPException(400, "Missing X-Device-Id header")
    return taste.analyze(device, n_predictions=predictions)
