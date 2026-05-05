import json

from app.config import BASE_DIR


DECOR_LIBRARY_PATH = BASE_DIR / "static" / "decor" / "decor_library.json"


def load_decor_library() -> list[dict]:
    try:
        with DECOR_LIBRARY_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(data, list):
        return []

    return [item for item in data if isinstance(item, dict)]


def get_enabled_decor_assets() -> list[dict]:
    return [item for item in load_decor_library() if item.get("enabled") is True]


def get_decor_assets_by_category(category: str) -> list[dict]:
    clean_category = (category or "").strip()
    return [
        item
        for item in get_enabled_decor_assets()
        if item.get("category") == clean_category
    ]
