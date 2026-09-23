# ============================================================
# SELF SCANNER - embedding_service.py (Track B core)
# Loads notebook artifacts and runs cover-similarity search
# with EXACTLY the notebook preprocessing.
# ============================================================
import os
import json

import numpy as np
import pandas as pd
from PIL import Image


class EmbeddingService:
    def __init__(self, artifacts_dir):
        self.artifacts_dir = artifacts_dir
        self.model = None
        self.embeddings = None
        self.class_map = None
        self.neighbors = None
        self.catalog = None
        self.ready = False

    def load(self):
        import tensorflow as tf  # heavy import, deferred

        model_path = os.path.join(self.artifacts_dir, "book_cover_model.keras")
        emb_path = os.path.join(self.artifacts_dir, "cover_embedding.npy")
        cmap_path = os.path.join(self.artifacts_dir, "class_map.csv")
        for p in (model_path, emb_path, cmap_path):
            if not os.path.exists(p):
                raise FileNotFoundError(
                    f"Missing artifact: {p}. Run backend/scripts/rebuild_artifacts.py"
                )

        print("Loading model (this takes ~10s)...", flush=True)
        self.model = tf.keras.models.load_model(model_path)
        self.embeddings = np.load(emb_path)
        self.class_map = pd.read_csv(cmap_path)

        nb_path = os.path.join(self.artifacts_dir, "neighbors.json")
        if os.path.exists(nb_path):
            with open(nb_path, encoding="utf-8") as f:
                self.neighbors = json.load(f)

        cat_path = os.path.join(self.artifacts_dir, "catalog.json")
        if os.path.exists(cat_path):
            with open(cat_path, encoding="utf-8") as f:
                self.catalog = json.load(f)

        self.ready = True
        print(
            f"EmbeddingService ready: {self.embeddings.shape[0]} books, "
            f"dim={self.embeddings.shape[1]}",
            flush=True,
        )

    # ---- notebook-identical preprocessing (STEP 2 load_image) ----
    @staticmethod
    def preprocess(pil_image: Image.Image) -> np.ndarray:
        img = pil_image.convert("RGB").resize((224, 224))
        return np.array(img, dtype=np.float32)

    def embed(self, pil_image: Image.Image) -> np.ndarray:
        if not self.ready:
            raise RuntimeError("EmbeddingService not loaded")
        batch = np.stack([self.preprocess(pil_image)])
        vec = self.model.predict(batch, verbose=0)[0].astype("float32")
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm > 0 else vec

    def search(self, pil_image: Image.Image, k: int = 5):
        """Return top-k most similar catalog entries (cosine = dot)."""
        q = self.embed(pil_image)
        scores = self.embeddings @ q
        top = np.argsort(scores)[::-1][:k]
        return [
            {"idx": int(i), "similarity": float(scores[int(i)])} for i in top
        ]

    def book(self, idx: int) -> dict:
        """Book info for embedding index idx (class_map + catalog merge)."""
        row = self.class_map.iloc[int(idx)]
        info = {
            "idx": int(idx),
            "slug": str(row["book_title"]),
            "title": str(row["book_title"]).replace("-", " ").replace("_", " "),
            "image": os.path.basename(str(row["image_path"])),
        }
        if self.catalog:
            try:
                info.update(self.catalog["books"][int(idx)])
            except (IndexError, KeyError):
                pass
        return info

    def neighbors_of(self, idx: int, k: int = 10):
        if self.neighbors is None:
            return []
        return [int(i) for i in self.neighbors[int(idx)][:k]]


# Singleton used by the app
service = EmbeddingService(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "artifacts")
)
