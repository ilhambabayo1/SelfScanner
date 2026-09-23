import os

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
ARTIFACTS_DIR = os.path.join(DATA_DIR, "artifacts")
COVERS_DIR = os.path.join(DATA_DIR, "covers")
DB_PATH = os.path.join(DATA_DIR, "db", "selfscanner.db")

def _load_env(path):
    """Tiny .env loader (KEY=VALUE lines); real env vars still win."""
    if os.path.exists(path):
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env(os.path.join(BACKEND_DIR, ".env"))

# Vision provider: Gemini (free tier). Mock mode without a key.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
GEMINI_MOCK = os.environ.get("GEMINI_MOCK", "0") == "1"

TOP_K_DEFAULT = 5
DAILY_SCAN_LIMIT = int(os.environ.get("DAILY_SCAN_LIMIT", "50"))
