# Standalone vision check: scans a real dataset cover and
# prints which provider answered. Run after setting your key:
#   $env:GEMINI_API_KEY = "..."
#   python backend/scripts/test_vision.py
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE)))

import pandas as pd

from app.config import GEMINI_API_KEY
from app.services.vision import active_provider, identify

print("provider in use:", active_provider())
if not GEMINI_API_KEY:
    print("(no key set - will answer in mock mode)")

cmap = pd.read_csv(
    os.path.join(os.path.dirname(HERE), "data", "artifacts", "class_map.csv")
)
img_path = cmap["image_path"].iloc[0]
print("scanning:", os.path.basename(img_path))

with open(img_path, "rb") as f:
    result = identify(f.read())

print(json.dumps(result, indent=2))
