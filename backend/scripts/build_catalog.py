# ============================================================
# SELF SCANNER - build_catalog.py (Phase 0)
# Merges class_map.csv -> catalog.json (UI-facing book list).
# Optional: --enrich adds Google Books metadata (resumable,
# cached in enrichment.json; safe to re-run with --limit).
# Run:  python backend/scripts/build_catalog.py
#       python backend/scripts/build_catalog.py --enrich --limit 200
# ============================================================
import os
import json
import time
import argparse

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
ART_DIR = os.path.join(BACKEND, "data", "artifacts")
ENRICH_PATH = os.path.join(ART_DIR, "enrichment.json")


def slug_to_query(slug):
    words = slug.replace("-", " ").replace("_", " ").strip()
    return " ".join(w for w in words.split() if not w.isdigit())


def fetch_google_books(client, title, author=None):
    q = f"intitle:{title}"
    if author:
        q += f"+inauthor:{author}"
    r = client.get(
        "https://www.googleapis.com/books/v1/volumes",
        params={"q": q, "maxResults": 1, "country": "US"},
        timeout=10,
    )
    if r.status_code == 429:
        time.sleep(5)
        return None
    r.raise_for_status()
    items = r.json().get("items") or []
    if not items:
        return None
    v = items[0].get("volumeInfo", {})
    return {
        "gb_title": v.get("title"),
        "gb_subtitle": v.get("subtitle"),
        "gb_authors": v.get("authors"),
        "gb_published": v.get("publishedDate"),
        "gb_categories": v.get("categories"),
        "gb_rating": v.get("averageRating"),
        "gb_cover": (v.get("imageLinks") or {}).get("thumbnail"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--enrich", action="store_true", help="fetch Google Books metadata")
    ap.add_argument("--limit", type=int, default=0, help="max new lookups this run")
    ap.add_argument("--sleep", type=float, default=0.15)
    args = ap.parse_args()

    df = pd.read_csv(os.path.join(ART_DIR, "class_map.csv"))
    manifest = {}
    mp = os.path.join(ART_DIR, "manifest.json")
    if os.path.exists(mp):
        manifest = json.load(open(mp, encoding="utf-8"))
    dataset_dir = manifest.get("dataset_dir") or os.path.dirname(
        df["image_path"].iloc[0]
    )

    books = [
        {
            "idx": int(i),
            "slug": row.book_title,
            "title": str(row.book_title).replace("-", " ").replace("_", " "),
            "image": os.path.basename(row.image_path),
        }
        for i, row in enumerate(df.itertuples())
    ]

    enrichment = {}
    if os.path.exists(ENRICH_PATH):
        enrichment = json.load(open(ENRICH_PATH, encoding="utf-8"))

    if args.enrich:
        import httpx

        client = httpx.Client()
        done = 0
        for b in books:
            slug = b["slug"]
            if slug in enrichment:
                continue
            if args.limit and done >= args.limit:
                break
            try:
                meta = fetch_google_books(client, slug_to_query(slug))
            except Exception as e:  # noqa: BLE001 - keep the bulk run alive
                print(f"  lookup failed for {slug}: {e}")
                meta = None
            if meta:
                enrichment[slug] = meta
                done += 1
            if done and done % 25 == 0:
                json.dump(enrichment, open(ENRICH_PATH, "w", encoding="utf-8"))
                print(f"  enriched {done} (cached; resumable)", flush=True)
            time.sleep(args.sleep)
        json.dump(enrichment, open(ENRICH_PATH, "w", encoding="utf-8"))
        client.close()

    for b in books:
        b.update(enrichment.get(b["slug"], {}))

    catalog = {
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset_dir": dataset_dir,
        "n_books": len(books),
        "enriched": sum(1 for b in books if b.get("gb_title")),
        "books": books,
    }
    out = os.path.join(ART_DIR, "catalog.json")
    json.dump(catalog, open(out, "w", encoding="utf-8"))
    print(f"saved {out}: {len(books)} books, {catalog['enriched']} enriched")


if __name__ == "__main__":
    main()
