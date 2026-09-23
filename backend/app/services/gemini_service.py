# ============================================================
# SELF SCANNER - gemini_service.py (Track A: identification)
# Gemini Vision via the Gemini REST API (generateContent) with
# inline base64 image and forced JSON output. Falls back to a
# deterministic mock without a key (or with GEMINI_MOCK=1).
# ============================================================
import base64
import json
import re
import time

import httpx

from ..config import GEMINI_API_KEY, GEMINI_MOCK, GEMINI_MODEL

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Tried in order until one responds; makes the service
# resilient to model renames across Gemini versions.
MODEL_CASCADE = [
    GEMINI_MODEL,
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
]
seen = set()
MODELS = [m for m in MODEL_CASCADE if not (m in seen or seen.add(m))]

PROMPT = """You are helping a book-scanner app identify a book from a photo of its cover.
Look at the image and respond with ONLY a JSON object (no markdown, no commentary) using this exact schema:
{
  "is_book_cover": true/false,
  "title": "exact title text visible on the cover, or best guess from cover art",
  "author": "author name if visible, else empty string",
  "isbn": "ISBN if printed on the cover, else empty string",
  "series": "series name if visible, else empty string",
  "visible_text": "all other text you can read on the cover",
  "age_band": "picture-book|early-reader|middle-grade|teen|young-adult|adult|unknown",
  "cover_style": "illustration|photographic|typographic|mixed",
  "dominant_colors": ["up to 3 color names"],
  "mood": "one or two words, e.g. playful, dark, calm",
  "themes": ["up to 3 themes, e.g. friendship, mystery, self-discovery"],
  "pace": "slow-burn|steady|fast-paced|unknown",
  "confidence": 0.0
}
Transcribe only text you can actually see - never invent a title. If unsure, lower confidence."""


def _media_type(image_bytes: bytes) -> str:
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:4] == b"GIF8":
        return "image/gif"
    if image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _extract_json(text: str) -> dict:
    """Parse the JSON object from a model response, tolerating
    markdown fences / commentary around it."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON in Gemini response: {text[:200]}")
    return json.loads(m.group(0))


def _mock_identify(image_bytes: bytes) -> dict:
    h = hash(image_bytes[:64]) % 1000
    return {
        "is_book_cover": True,
        "title": f"Mock Book {h}",
        "author": "Mock Author",
        "isbn": "",
        "series": "",
        "visible_text": "",
        "age_band": "middle-grade",
        "cover_style": "illustration",
        "dominant_colors": ["blue", "yellow"],
        "mood": "playful",
        "themes": ["friendship", "adventure"],
        "pace": "steady",
        "confidence": 0.42,
        "_mock": True,
    }


def identify(image_bytes: bytes, timeout: float = 30.0) -> dict:
    """Gemini Vision: cover photo -> structured identification dict."""
    if GEMINI_MOCK or not GEMINI_API_KEY:
        return _mock_identify(image_bytes)

    # Gemini guidance: text prompt BEFORE the image part
    body = {
        "contents": [
            {
                "parts": [
                    {"text": PROMPT},
                    {
                        "inline_data": {
                            "mime_type": _media_type(image_bytes),
                            "data": base64.standard_b64encode(image_bytes).decode(),
                        }
                    },
                ]
            }
        ],
        "generationConfig": {"response_mime_type": "application/json", "temperature": 0.1},
    }
    last_err = None
    for model in MODELS:
        url = f"{API_BASE}/{model}:generateContent"
        # Free-tier flash models often answer 503 "high demand";
        # retry each model once with a short backoff before moving on.
        for attempt in (1, 2):
            try:
                resp = httpx.post(
                    url,
                    json=body,
                    headers={"x-goog-api-key": GEMINI_API_KEY,
                             "content-type": "application/json"},
                    timeout=timeout,
                )
                if resp.status_code == 404:  # model unavailable -> next model
                    last_err = f"{model}: 404"
                    break
                if resp.status_code in (429, 503):  # busy -> brief backoff
                    last_err = f"{model}: HTTP {resp.status_code} (busy)"
                    time.sleep(1.5 * attempt)
                    continue
                resp.raise_for_status()
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                result = _extract_json(text)
                result["model"] = model
                result["provider"] = "gemini"
                return result
            except Exception as e:  # noqa: BLE001 - try next model, then mock
                last_err = f"{model}: {e}"
                break
    # Every model failed - degrade to mock rather than break the scan
    out = _mock_identify(image_bytes)
    out["_error"] = str(last_err)
    return out
