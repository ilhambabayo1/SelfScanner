# ============================================================
# SELF SCANNER - taste_service.py (Track C: personalization)
# Smart pattern recognition + predicted ratings:
#  - taste vector: embedding centroid weighted by ratings
#  - attribute patterns: mood/pace/themes lifts vs chance
#  - predicted rating = user mean + affinity adjustment
# ============================================================
import json
import os

import numpy as np

from .embedding_service import service as emb
from .. import db


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


class TasteService:
    """Learns hidden preferences from a device's ratings and shelf."""

    FIELD_LABELS = {
        "mood": "mood",
        "pace": "narrative pace",
        "themes": "theme",
        "cover_style": "cover style",
        "age_band": "audience",
    }
    STATUS_Y = {"completed": 4.2, "reading": 3.8, "want-to-read": 3.1}

    def __init__(self, emb_service, db_module):
        self.emb = emb_service
        self.db = db_module

    def _slug_to_idx(self):
        cm = self.emb.class_map
        return {str(t).strip(): int(i) for i, t in enumerate(cm["book_title"].astype(str))}

    def analyze(self, device: str, n_predictions: int = 6) -> dict:
        out = {"ready": False,
               "stats": {"n_rated": 0, "avg": None, "confidence": 0.0},
               "patterns": [], "predictions": []}
        if not self.emb.ready or not device:
            return out

        rows = self.db.shelf_rows(device)
        meta = self.db.scan_meta(device)
        slug_to_idx = self._slug_to_idx()
        E = self.emb.embeddings

        entries, shelf_keys = [], set()
        for r in rows:
            shelf_keys.add(r["book_key"])
            idx = slug_to_idx.get(str(r["book_key"]).strip())
            if idx is None:
                continue
            y = float(r["rating"]) if r["rating"] else self.STATUS_Y.get(r["status"], 3.0)
            entries.append({"idx": idx, "key": r["book_key"], "y": y,
                            "rating": r["rating"], "status": r["status"]})

        ratings = [e["y"] for e in entries if e["rating"]]
        out["ready"] = True
        out["stats"] = {
            "n_rated": len(ratings),
            "n_interactions": len(entries),
            "avg": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "confidence": round(min(1.0, len(ratings) / 8.0), 2),
        }

        # ---- patterns from identified cover attributes ----
        field_weights = {}
        for e in entries:
            raw = meta.get(e["idx"])
            if not raw:
                continue
            try:
                m = json.loads(raw)
            except (ValueError, TypeError):
                continue
            w = _clip(e["y"] - 3.0, -2.0, 2.0) / 2.0  # -1..+1 like/dislike weight
            for field in self.FIELD_LABELS:
                vals = m.get(field)
                if field == "themes" and isinstance(vals, list):
                    vals = [str(v).lower() for v in vals][:3]
                elif isinstance(vals, str) and vals and vals != "unknown":
                    vals = [str(vals).lower()]
                else:
                    continue
                d = field_weights.setdefault(field, {})
                for v in vals:
                    d[v] = d.get(v, 0.0) + max(w, 0.05)

        patterns = []
        for field, values in field_weights.items():
            total = sum(values.values())
            k = max(1, len(values))
            for v, w in values.items():
                lift = (w / total) * k  # >1 = over-represented vs uniform
                if lift >= 1.35 and w >= 0.9:
                    patterns.append({
                        "field": field, "value": v,
                        "label": self.FIELD_LABELS[field],
                        "lift": round(lift, 2),
                        "text": "You keep rating “" + v + "" "" + self.FIELD_LABELS[field] +
                                "” books higher (" + format(lift, ".1f") + "x more than chance)",
                    })
        patterns.sort(key=lambda p: -p["lift"])
        out["patterns"] = patterns[:6]

        # ---- taste vector (embedding centroid) ----
        vec = np.zeros(E.shape[1], dtype=np.float32)
        used = 0
        for e in entries:
            w = _clip(e["y"] - 3.0, -2.0, 2.0) / 2.0
            if abs(w) < 0.01:
                continue
            vec += w * E[e["idx"]]
            used += 1
        if used == 0 or not np.linalg.norm(vec) > 0:
            return out  # not enough signal yet
        vec = vec / np.linalg.norm(vec)

        sims = E @ vec
        liked_idx = [e["idx"] for e in entries if e["y"] >= 3.8]
        mean_liked = float(np.mean(sims[liked_idx])) if liked_idx else 0.55
        user_mean = out["stats"]["avg"] if out["stats"]["avg"] else 3.6

        # ---- predicted ratings for unread books ----
        preds = []
        for i in np.argsort(-sims):
            idx = int(i)
            slug = str(self.emb.class_map["book_title"].iloc[idx]).strip()
            if not slug or slug in shelf_keys:
                continue
            sim = float(sims[idx])
            predicted = _clip(user_mean + 2.2 * (sim - mean_liked), 1.0, 5.0)
            why = "matches your taste profile"
            if liked_idx:
                j = int(np.argmax(E[liked_idx] @ E[idx]))
                why = "sits closest to “" + str(self.emb.book(liked_idx[j])["title"]).strip() + "”"
            preds.append({
                "idx": idx, "book_key": slug,
                "title": str(self.emb.book(idx)["title"]),
                "image": os.path.basename(str(self.emb.class_map["image_path"].iloc[idx])),
                "similarity": round(sim, 4),
                "predicted": round(predicted, 1),
                "why": why,
            })
            if len(preds) >= max(1, n_predictions):
                break
        out["predictions"] = preds
        return out


# Singleton used by the app
service = TasteService(emb, db)
