# ============================================================
# SELF SCANNER - main.py (FastAPI app)
# Run:  uvicorn app.main:app --reload --port 8000   (from backend/)
# ============================================================
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .routers import scanner, shelf, taste
from .services.embedding_service import service as emb

app = FastAPI(title="Self Scanner API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scanner.router)
app.include_router(shelf.router)
app.include_router(taste.router)


@app.on_event("startup")
def _startup():
    db.init_db()
    # Heavy TF model load in background thread so the server binds fast
    threading.Thread(target=_load_engine, daemon=True).start()


def _load_engine():
    try:
        emb.load()
    except Exception as e:  # noqa: BLE001
        print(f"ENGINE LOAD FAILED: {e}", flush=True)

# ---- Static UI (served at /) ----
import os

from fastapi.staticfiles import StaticFiles

_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static"
)
app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="ui")
