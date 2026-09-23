# ============================================================
# SELF SCANNER - build_neighbors.py (Phase 0)
# Precomputes top-K nearest neighbors (cosine) for every cover.
# Output: backend/data/artifacts/neighbors.json  ([[idx,...], ...])
# Run:  python backend/scripts/build_neighbors.py
# ============================================================
import os
import json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
ART_DIR = os.path.join(BACKEND, "data", "artifacts")
K = 10
CHUNK = 512


def main():
    emb_path = os.path.join(ART_DIR, "cover_embedding.npy")
    emb = np.load(emb_path)
    n = emb.shape[0]
    print(f"loaded embeddings {emb.shape}; computing top-{K} neighbors for {n} books")

    neighbors = np.zeros((n, K), dtype=np.int64)
    for start in range(0, n, CHUNK):
        end = min(start + CHUNK, n)
        sims = emb[start:end] @ emb.T  # (chunk, n)
        rows = np.arange(start, end)
        sims[np.arange(end - start), rows] = -np.inf  # exclude self
        part = np.argpartition(-sims, K, axis=1)[:, :K]
        part_scores = np.take_along_axis(sims, part, axis=1)
        order = np.argsort(-part_scores, axis=1)
        neighbors[start:end] = np.take_along_axis(part, order, axis=1)
        if (start // CHUNK) % 4 == 0:
            print(f"  progress: {end}/{n}", flush=True)

    out = os.path.join(ART_DIR, "neighbors.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(neighbors.tolist(), f)
    print("saved", out)


if __name__ == "__main__":
    main()
