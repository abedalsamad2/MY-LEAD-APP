import json
import os
from config import CACHE_DIR


def load_cache(domain: str) -> dict | None:
    """Load cached result for a domain if it exists."""
    path = f"{CACHE_DIR}/{domain}.json"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def save_cache(domain: str, data: dict):
    """Save result for a domain to cache."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(f"{CACHE_DIR}/{domain}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_progress() -> dict:
    """Load overall run progress (which URLs are done)."""
    from config import PROGRESS_FILE

    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"completed": [], "results": []}


def save_progress(progress: dict):
    """Save run progress so tool can resume if interrupted."""
    from config import PROGRESS_FILE

    os.makedirs("output", exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)
