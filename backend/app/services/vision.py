# ============================================================
# SELF SCANNER - vision.py (Track A: identification entry point)
# Gemini Vision (free tier) via gemini_service. Mock mode when
# no GEMINI_API_KEY is set or GEMINI_MOCK=1.
# ============================================================
from ..config import GEMINI_API_KEY, GEMINI_MOCK
from . import gemini_service


def active_provider() -> str:
    if GEMINI_MOCK or not GEMINI_API_KEY:
        return "mock"
    return "gemini"


def identify(image_bytes: bytes, timeout: float = 30.0) -> dict:
    return gemini_service.identify(image_bytes, timeout=timeout)
