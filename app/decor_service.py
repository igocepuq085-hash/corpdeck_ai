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


DECOR_CATEGORY_KEYWORDS = {
    "transport": [
        "поезд",
        "локомотив",
        "вагон",
        "цистерн",
        "станция",
        "маршрут",
        "движение",
        "расписание",
        "транспорт",
        "логистика",
        "рельс",
        "перегон",
    ],
    "finance": [
        "экономия",
        "бюджет",
        "инвестиции",
        "стоимость",
        "эффект",
        "деньги",
        "руб",
        "млн",
        "тыс",
        "окупаемость",
        "финансы",
    ],
    "safety": [
        "безопасность",
        "риск",
        "охрана труда",
        "сиз",
        "контроль",
        "проверка",
        "инцидент",
        "нарушение",
    ],
    "digital": [
        "цифров",
        "система",
        "мониторинг",
        "интерфейс",
        "данные",
        "ит",
        "автоматизация",
        "vr",
        "искусственный интеллект",
    ],
    "education": [
        "обучение",
        "тренировка",
        "знания",
        "тестирование",
        "экзамен",
        "персонал",
        "развитие",
    ],
    "production": [
        "производство",
        "объект",
        "оборудование",
        "цех",
        "площадка",
        "промышленный",
        "технологический процесс",
    ],
    "hr": [
        "команда",
        "роли",
        "участники",
        "руководитель",
        "персонал",
        "компетенции",
        "организационная структура",
    ],
    "analytics": [
        "аналитика",
        "показатель",
        "динамика",
        "график",
        "таблица",
        "kpi",
        "данные",
        "результат",
        "сравнение",
    ],
    "strategy": [
        "цель",
        "стратегия",
        "дорожная карта",
        "этап",
        "план",
        "внедрение",
        "решение",
        "приоритет",
    ],
}

DOMAIN_TO_DECOR_CATEGORY = {
    "transport": "transport",
    "finance": "finance",
    "investment": "finance",
    "safety": "safety",
    "it_digital": "digital",
    "education": "education",
    "production": "production",
    "construction": "production",
    "hr": "hr",
    "marketing": "analytics",
    "sales": "analytics",
    "project_management": "strategy",
    "legal_compliance": "safety",
}


def detect_decor_category_for_slide(slide: dict, deck_plan: dict) -> str:
    content = slide.get("content") if isinstance(slide.get("content"), dict) else {}
    bullets = content.get("bullets") if isinstance(content.get("bullets"), list) else []
    detected_context = deck_plan.get("detected_context") if isinstance(deck_plan.get("detected_context"), dict) else {}
    domain = str(detected_context.get("domain") or "").strip()

    text_parts = [
        slide.get("title", ""),
        slide.get("subtitle", ""),
        slide.get("main_message", ""),
        slide.get("main_fact", ""),
        " ".join(str(item) for item in bullets),
        domain,
    ]
    text = " ".join(str(item) for item in text_parts).lower()

    scores = {}
    for category, keywords in DECOR_CATEGORY_KEYWORDS.items():
        scores[category] = sum(1 for keyword in keywords if keyword.lower() in text)

    best_category = max(scores, key=scores.get)
    if scores[best_category] > 0:
        return best_category

    return DOMAIN_TO_DECOR_CATEGORY.get(domain, "general")


def choose_decor_layer_for_slide(slide: dict, deck_plan: dict) -> dict:
    category = detect_decor_category_for_slide(slide, deck_plan)
    assets = get_decor_assets_by_category(category)
    if assets:
        asset = assets[0]
        return {
            "enabled": True,
            "category": category,
            "asset_id": asset.get("id", ""),
            "file": asset.get("file", ""),
            "placement": asset.get("placement", "right-soft"),
            "intensity": asset.get("intensity", "low"),
        }

    return {
        "enabled": False,
        "category": category,
        "asset_id": "",
        "file": "",
        "placement": "right-soft",
        "intensity": "low",
    }


def attach_decor_layers_to_deck_plan(deck_plan: dict) -> dict:
    slides = deck_plan.get("slides") if isinstance(deck_plan.get("slides"), list) else []
    last_index = len(slides) - 1

    for index, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        if index == 0 or index == last_index:
            slide["decorative_layer"] = {
                "enabled": False,
                "category": "general",
                "asset_id": "",
                "file": "",
                "placement": "none",
                "intensity": "low",
            }
        else:
            slide["decorative_layer"] = choose_decor_layer_for_slide(slide, deck_plan)

    return deck_plan
