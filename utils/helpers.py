import json
import os

def load_data(path: str):
    """Return parsed JSON or [] if file missing/invalid."""
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_data(path: str, data):
    """Write JSON to path (create dirs if needed)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)