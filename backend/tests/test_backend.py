# ============================================================
# SELF SCANNER - test_backend.py
# Validation gates:
#  1. Artifacts exist and have notebook shapes
#  2. Track B self-consistency: embedding a dataset cover
#     returns ITSELF as top-1 (similarity ~1.0)
#  3. Top-5 similarities land in the healthy 0.5-1.0 band
#  4. Gemini service works in mock mode
#  5. Full /api/scan hybrid endpoint returns identified + matches
# Run:  python -m pytest backend/tests/test_backend.py -v
# ============================================================
import io
import os
import sys
import time
import json

import numpy as np
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ART = os.path.join(BACKEND, "backend", "data", "artifacts")
sys.path.insert(0, os.path.join(BACKEND, "backend"))


def test_artifacts_exist():
    for f in ("cover_embedding.npy", "class_map.csv", "book_cover_model.keras"):
        assert os.path.exists(os.path.join(ART, f)), f"missing artifact {f}"
    emb = np.load(os.path.join(ART, "cover_embedding.npy"))
    assert emb.shape == (6232, 2048), f"unexpected shape {emb.shape}"
    # rows must be unit-normalized (notebook gate)
    norms = np.linalg.norm(emb, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3), f"rows not normalized: {norms[:3]}"


@pytest.fixture(scope="session")
def engine():
    from app.services.embedding_service import service

    if not service.ready:
        service.load()
    return service


def test_track_b_self_retrieval(engine):
    """Embed a real dataset cover; it must find itself at #1."""
    import pandas as pd
    from PIL import Image

    cmap = pd.read_csv(os.path.join(ART, "class_map.csv"))
    probe_idx = 0
    img = Image.open(cmap["image_path"].iloc[probe_idx]).convert("RGB")
    results = engine.search(img, k=5)
    assert len(results) == 5
    assert results[0]["idx"] == probe_idx, "cover did not retrieve itself"
    assert results[0]["similarity"] > 0.99, f"self-sim too low: {results[0]}"
    for r in results[1:]:
        assert 0.4 < r["similarity"] < 1.0, f"similarity out of band: {r}"


def test_neighbors_consistent(engine):
    if engine.neighbors is None:
        pytest.skip("neighbors.json not built yet")
    nb = engine.neighbors_of(0, k=5)
    assert len(nb) == 5
    assert 0 not in nb, "neighbor list must exclude the book itself"


def test_gemini_mock_mode(monkeypatch):
    """Mock path must work even if a real key exists in the env."""
    import app.services.gemini_service as gs

    monkeypatch.setattr(gs, "GEMINI_API_KEY", "")
    monkeypatch.setattr(gs, "GEMINI_MOCK", False)
    out = gs.identify(b"\xff\xd8\xff_fakejpeg")
    assert out["is_book_cover"] is True
    assert out.get("_mock") is True
    assert 0.0 <= out["confidence"] <= 1.0


def test_scan_endpoint(engine):
    from fastapi.testclient import TestClient
    from app.main import app
    import pandas as pd

    cmap = pd.read_csv(os.path.join(ART, "class_map.csv"))
    with open(cmap["image_path"].iloc[0], "rb") as f:
        img_bytes = f.read()

    client = TestClient(app)
    r = client.post(
        "/api/scan",
        files={"file": ("cover.jpg", img_bytes, "image/jpeg")},
        data={"device_id": "test-device-123"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "identified" in body and "similar_books" in body
    assert len(body["similar_books"]) == 5
    top = body["similar_books"][0]
    assert top["similarity"] > 0.99
    assert top["idx"] == 0

    # shelf round-trip
    r2 = client.post(
        "/api/shelf/9780007425082-1-",
        params={"status": "want-to-read"},
        headers={"X-Device-Id": "test-device-123"},
    )
    assert r2.status_code == 200
    r3 = client.get("/api/shelf", headers={"X-Device-Id": "test-device-123"})
    assert r3.status_code == 200
    assert any(i["book_key"] == "9780007425082-1-" for i in r3.json()["items"])


def test_taste_profile_and_predictions():
    """Gate 6: ratings must produce patterns and predicted ratings."""
    from fastapi.testclient import TestClient
    from app.main import app
    import pandas as pd

    cmap = pd.read_csv(os.path.join(ART, "class_map.csv"))

    def slug(i):
        return str(cmap["book_title"].iloc[i]).strip()

    client = TestClient(app)
    H = {"X-Device-Id": "taste-test-1"}
    assert client.post("/api/rate/" + slug(0), params={"rating": 5}, headers=H).status_code == 200
    assert client.post("/api/rate/" + slug(123), params={"rating": 2}, headers=H).status_code == 200

    prof = client.get("/api/profile?predictions=5", headers=H).json()
    assert prof["ready"] is True
    assert prof["stats"]["n_rated"] >= 2
    assert prof["stats"]["avg"] is not None

    preds = prof["predictions"]
    assert len(preds) == 5
    rated_keys = {slug(0), slug(123)}
    for p in preds:
        assert 1.0 <= p["predicted"] <= 5.0
        assert p["book_key"] not in rated_keys, "predictions must skip shelved books"
        assert p["why"]
