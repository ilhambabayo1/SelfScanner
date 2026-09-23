# ============================================================
# SELF SCANNER - google_books.py (Phase 4 metadata enrichment)
# Title/author -> clean metadata via Google Books API,
# cached in SQLite metadata_cache (30-day TTL logic in caller).
# ============================================================
import json

import requests

from .. import db

GB_URL = "https://www.googleapis.com/books/v1/volumes"


def _query(title: str, author=None) -> dict:
    q = f"intitle:{title}"
    if author:
        q += f"+inauthor:{author}"
    r = requests.get(
        GB_URL,
        params={"q": q, "maxResults": 3, "country": "US"},
        timeout=10,
    )
    r.raise_for_status()
    items = r.json().get("items") or []
    if not items:
        return {}
    v = items[0].get("volumeInfo", {})
    return {
        "title": v.get("title"),
        "subtitle": v.get("subtitle"),
        "authors": v.get("authors") or [],
        "publisher": v.get("publisher"),
        "published": v.get("publishedDate"),
        "categories": v.get("categories") or [],
        "rating": v.get("averageRating"),
        "description": (v.get("description") or "")[:400],
        "cover": (v.get("imageLinks") or {}).get("thumbnail"),
    }


def lookup(title: str, author=None) -> dict:
    """Cached metadata lookup; returns {} when nothing found."""
    key = f"gb:{(title or '').lower().strip()}|{(author or '').lower().strip()}"
    cached = db.cache_get(key)
    if cached:
        return json.loads(cached)
    try:
        meta = _query(title, author)
    except Exception:  # noqa: BLE001 - metadata is best-effort
        meta = {}
    db.cache_set(key, json.dumps(meta))
    return meta
