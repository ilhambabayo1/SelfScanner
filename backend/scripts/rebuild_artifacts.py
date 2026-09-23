# ============================================================
# SELF SCANNER - rebuild_artifacts.py (Phase 0)
# Reproduces the Colab notebook pipeline locally:
#   dataset -> ResNet50 embeddings -> normalize -> save artifacts
# Outputs (backend/data/artifacts/):
#   cover_embedding.npy, class_map.csv, book_cover_model.keras
# Run:  python backend/scripts/rebuild_artifacts.py
# ============================================================
import os
import sys
import time
import json

import numpy as np
import pandas as pd
import tensorflow as tf
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
ART_DIR = os.path.join(BACKEND, "data", "artifacts")
os.makedirs(ART_DIR, exist_ok=True)

BATCH = 64


def main():
    t0 = time.time()
    import kagglehub

    path = kagglehub.dataset_download(
        "thomaskonstantin/6000-children-and-teen-book-covers"
    )
    bookcovers_path = os.path.join(path, "BookCovers")
    image_files = [f for f in os.listdir(bookcovers_path) if f.endswith(".jpg")]
    df = pd.DataFrame(
        {
            "image_filename": image_files,
            "image_path": [os.path.join(bookcovers_path, f) for f in image_files],
        }
    )
    df["book_title"] = df["image_filename"].str.removesuffix(".jpg")
    print(f"df built: {len(df)} covers")

    # Same model as notebook STEP 1
    base = tf.keras.applications.ResNet50(
        include_top=False, pooling="avg", weights="imagenet"
    )
    inputs = tf.keras.Input(shape=(224, 224, 3))
    x = tf.keras.applications.resnet50.preprocess_input(inputs)
    outputs = base(x)
    model = tf.keras.Model(inputs, outputs, name="cover_embedding_model")

    # Same preprocessing as notebook STEP 2
    def load_image(p):
        img = Image.open(p).convert("RGB").resize((224, 224))
        return np.array(img, dtype=np.float32)

    paths = df["image_path"].tolist()
    print(f"Embedding {len(paths)} covers on CPU (this can take a while)...")
    all_embeddings = []
    for i in range(0, len(paths), BATCH):
        batch = np.stack([load_image(p) for p in paths[i : i + BATCH]])
        embs = model.predict(batch, verbose=0)
        all_embeddings.append(embs)
        if (i // BATCH) % 10 == 0:
            print(f"  progress: {i + len(batch)}/{len(paths)}", flush=True)

    all_embeddings = np.vstack(all_embeddings).astype("float32")
    print("Embeddings shape:", all_embeddings.shape)

    norms = np.linalg.norm(all_embeddings, axis=1, keepdims=True)
    embeddings_norm = all_embeddings / norms

    np.save(os.path.join(ART_DIR, "cover_embedding.npy"), embeddings_norm)
    df[["book_title", "image_path"]].to_csv(
        os.path.join(ART_DIR, "class_map.csv"), index=False
    )
    model.save(os.path.join(ART_DIR, "book_cover_model.keras"))

    manifest = {
        "n_books": int(len(df)),
        "embedding_dim": int(embeddings_norm.shape[1]),
        "tf_version": tf.__version__,
        "dataset_dir": bookcovers_path,
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(ART_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("Saved artifacts to:", ART_DIR)
    print(f"DONE in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    sys.exit(main())
