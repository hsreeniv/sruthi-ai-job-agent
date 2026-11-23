import json
from pathlib import Path

PROFILE_PATH = Path("data/profile.json")

def load_profile():
    if not PROFILE_PATH.exists():
        raise FileNotFoundError("Missing data/profile.json")
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
