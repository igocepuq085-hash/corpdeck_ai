import base64
from pathlib import Path

from openai import OpenAI

from app.config import BASE_DIR, OPENAI_API_KEY, OPENAI_IMAGE_MODEL


CATEGORY_KEYWORDS = {
    "infrastructure": [
        "инфраструктура",
        "маршрут",
        "сеть",
        "логистика",
        "перевозк",
        "магистраль",
        "филиал",
        "регион",
    ],
    "rolling_stock": ["локомотив", "вагон", "цистерн", "подвижн", "состав", "поезд"],
    "safety": ["безопасность", "охрана труда", "риск", "опасность", "сиз", "высот", "контроль", "проверка"],
    "digital_control": [
        "цифров",
        "vr",
        "виртуальн",
        "тренажер",
        "тренажёр",
        "технология",
        "мониторинг",
        "система",
        "управление",
        "диспетчер",
        "аналитика в реальном времени",
    ],
    "analytics": ["показатель", "данные", "аналитика", "результат", "динамика", "эффективность", "kpi", "график", "таблица"],
    "training": ["обучение", "подготовка", "развитие", "тестирование", "сценарий", "тренировка", "экзамен"],
    "project_management": ["этап", "план", "дорожная карта", "срок", "реализация", "проект", "внедрение"],
    "team": ["команда", "участники", "руководитель", "куратор", "заказчик", "администратор"],
    "industrial_environment": ["производство", "объект", "промышленн", "станция", "эстакада", "цех", "площадка"],
    "document_process": ["документ", "регламент", "инструкция", "методика", "локальный акт", "согласование"],
}

CATEGORY_PRIORITY = [
    "safety",
    "digital_control",
    "rolling_stock",
    "infrastructure",
    "analytics",
    "training",
    "project_management",
    "industrial_environment",
    "team",
    "document_process",
    "general_corporate",
]

CATEGORY_SCENES = {
    "infrastructure": "железнодорожная инфраструктура, маршруты и логистика",
    "rolling_stock": "локомотивы, вагоны и подвижной состав",
    "safety": "промышленная безопасность, контроль и защита",
    "digital_control": "цифровое управление, VR и диспетчеризация",
    "analytics": "данные, аналитика и мониторинг показателей",
    "training": "обучение персонала и тренировка навыков",
    "project_management": "управление проектом, этапы и внедрение",
    "team": "корпоративная команда и координация специалистов",
    "industrial_environment": "промышленная площадка и железнодорожный объект",
    "document_process": "регламенты, документы и цифровой документооборот",
    "general_corporate": "универсальный корпоративный технологичный акцент",
}

CATEGORY_HINTS = {
    "infrastructure": "маршрут, рельсовый узел, логистический коридор, карта перевозок",
    "rolling_stock": "лаконичный локомотив, вагон, цистерна или состав без логотипов",
    "safety": "щит безопасности, каска, контрольная отметка, защитный контур",
    "digital_control": "VR-шлем, дисплей мониторинга, цифровой пульт, интерфейс управления",
    "analytics": "диаграмма, панель данных, график, KPI-индикатор",
    "training": "обучающий модуль, сценарий тренировки, наставник и цифровой тренажер",
    "project_management": "этапы проекта, дорожная карта, координация, внедрение",
    "team": "деловое взаимодействие специалистов, согласованная работа",
    "industrial_environment": "промышленный объект, станция, инфраструктурный узел",
    "document_process": "документ, регламент, планшет, согласование",
    "general_corporate": "синий технологичный корпоративный символ",
}

ASSET_TYPE_FILE_PARTS = {
    "icon": "icon",
    "mini_illustration": "mini",
    "thematic_accent": "accent",
}


def detect_slide_visual_category(slide: dict, deck_plan: dict) -> dict:
    strategy = detect_slide_asset_strategy(slide, deck_plan)
    return {
        "category": strategy["category"],
        "scene": strategy["scene"],
        "keywords": strategy["keywords"],
        "image_mode": "side-accent",
    }


def detect_slide_asset_strategy(slide: dict, deck_plan: dict) -> dict:
    content = slide.get("content") or {}
    context = deck_plan.get("detected_context") or {}
    text_parts = [
        slide.get("title", ""),
        slide.get("subtitle", ""),
        content.get("speaker_note", ""),
        " ".join(str(item) for item in content.get("bullets") or []),
        context.get("main_theme", ""),
        context.get("domain", ""),
    ]
    matches = _find_category_matches(" ".join(text_parts).lower())

    category = "general_corporate"
    for candidate in CATEGORY_PRIORITY:
        if candidate in matches:
            category = candidate
            break

    layout = slide.get("layout") or ""
    slide_type = slide.get("type") or ""
    layout_key = _normalize_layout(slide)
    asset_type = "thematic_accent"
    count = 1
    placement = "side-note"

    if layout_key == "cards":
        asset_type = "icon"
        count = 3
        placement = "card-header"
    elif layout_key == "analytics":
        asset_type = "icon"
        count = 3
        placement = "kpi-row"
    elif layout_key == "timeline":
        asset_type = "icon"
        count = 5
        placement = "timeline-node"
    elif layout_key == "risks":
        asset_type = "icon"
        count = 3
        placement = "card-header"
    elif layout_key == "text":
        asset_type = "mini_illustration" if category in {"training", "digital_control", "industrial_environment"} else "thematic_accent"
        count = 1
        placement = "top-right-small" if not slide.get("needs_table") else "side-note"
    elif slide_type == "section":
        asset_type = "thematic_accent"
        count = 1
        placement = "section-accent"

    if layout in {"data"} and slide.get("needs_chart"):
        placement = "chart-corner"
    if layout in {"data"} and slide.get("needs_table") and not slide.get("needs_chart"):
        placement = "table-corner"

    return {
        "category": category,
        "scene": CATEGORY_SCENES[category],
        "keywords": matches.get(category, []),
        "recommended_asset_type": asset_type,
        "recommended_count": count,
        "placement": placement,
    }


def select_slides_for_png_assets(deck_plan: dict, max_assets: int = 8) -> list[dict]:
    slides = deck_plan.get("slides") or []
    if not slides or max_assets <= 0:
        return []

    last_number = slides[-1].get("number")
    priorities = ["text", "cards", "analytics", "timeline", "risks"]
    selected = []
    planned_assets = 0

    for wanted_layout in priorities:
        for slide in slides:
            if slide.get("number") in {1, last_number}:
                continue
            if slide in selected:
                continue
            if _normalize_layout(slide) != wanted_layout:
                continue

            strategy = detect_slide_asset_strategy(slide, deck_plan)
            planned = max(1, min(strategy["recommended_count"], max_assets - planned_assets))
            selected.append({**slide, "_asset_strategy": {**strategy, "recommended_count": planned}})
            planned_assets += planned
            if planned_assets >= max_assets:
                return selected

    return selected


def generate_slide_png_assets(
    project_id: str,
    deck_plan: dict,
    brand_config: dict,
    max_assets: int = 8,
) -> list[dict]:
    selected_slides = select_slides_for_png_assets(deck_plan, max_assets=max_assets)
    if not selected_slides or not OPENAI_API_KEY:
        return []

    output_dir = BASE_DIR / "static" / "generated" / project_id
    output_dir.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=OPENAI_API_KEY)
    results = []

    for slide in selected_slides:
        strategy = slide.get("_asset_strategy") or detect_slide_asset_strategy(slide, deck_plan)
        asset_count = max(1, min(int(strategy.get("recommended_count") or 1), max_assets - len(results)))

        for asset_index in range(1, asset_count + 1):
            if len(results) >= max_assets:
                return results

            asset_type = strategy.get("recommended_asset_type", "thematic_accent")
            file_part = ASSET_TYPE_FILE_PARTS.get(asset_type, "accent")
            slide_number = int(slide.get("number") or 0)
            file_name = f"slide_{slide_number:02d}_{file_part}_{asset_index:02d}.png"
            local_path = output_dir / file_name
            image_path = f"/static/generated/{project_id}/{file_name}"
            prompt = build_png_asset_prompt(slide, deck_plan, brand_config, strategy)

            try:
                response = client.images.generate(
                    model=OPENAI_IMAGE_MODEL,
                    prompt=prompt,
                    size="1024x1024",
                    n=1,
                )
                image_data = response.data[0]
                b64_json = getattr(image_data, "b64_json", None)
                if not b64_json:
                    raise RuntimeError("OpenAI Image API не вернул PNG в base64")

                local_path.write_bytes(base64.b64decode(b64_json))
                results.append(
                    {
                        "slide_number": slide_number,
                        "asset_type": asset_type,
                        "category": strategy["category"],
                        "scene": strategy["scene"],
                        "image_path": image_path,
                        "local_path": str(Path("static") / "generated" / project_id / file_name),
                        "placement": strategy["placement"],
                        "prompt_brief": prompt,
                        "status": "ok",
                    }
                )
            except Exception as error:
                results.append(
                    {
                        "slide_number": slide_number,
                        "asset_type": asset_type,
                        "category": strategy["category"],
                        "scene": strategy["scene"],
                        "image_path": "",
                        "local_path": "",
                        "placement": strategy["placement"],
                        "prompt_brief": prompt,
                        "status": "error",
                        "error": str(error),
                    }
                )

    return results


def build_png_asset_prompt(
    slide: dict,
    deck_plan: dict,
    brand_config: dict,
    asset_strategy: dict,
) -> str:
    title = slide.get("title") or deck_plan.get("topic") or "корпоративная презентация"
    subtitle = slide.get("subtitle") or ""
    content = slide.get("content") or {}
    bullets = content.get("bullets") or []
    colors = brand_config.get("colors", {})
    asset_type = asset_strategy.get("recommended_asset_type", "thematic_accent")
    category = asset_strategy.get("category", "general_corporate")
    scene = asset_strategy.get("scene", CATEGORY_SCENES["general_corporate"])

    type_instruction = {
        "icon": (
            "Тип объекта: чистая PNG-иконка или пиктограмма. Простой силуэт, корпоративный линейный стиль, "
            "квадратная композиция, прозрачный или чистый светлый фон, без лишних деталей."
        ),
        "mini_illustration": (
            "Тип объекта: небольшая тематическая мини-иллюстрация. Компактная композиция, прозрачный или очень "
            "чистый светлый фон, подходит для вставки в угол слайда."
        ),
        "thematic_accent": (
            "Тип объекта: небольшой тематический PNG-акцент. Это может быть лаконичный объект по теме: маршрут, "
            "щит безопасности, цифровой интерфейс, схема, мониторинг или железнодорожный элемент."
        ),
    }.get(asset_type, "Тип объекта: небольшой тематический PNG-акцент.")

    return (
        "Создай небольшой PNG-элемент для корпоративной презентации. "
        f"Тема слайда: {title}. "
        f"Подзаголовок: {subtitle}. "
        f"Смысловые тезисы: {'; '.join(str(item) for item in bullets[:3])}. "
        f"Категория: {category}. Сцена: {scene}. "
        f"Визуальная логика: {CATEGORY_HINTS.get(category, CATEGORY_HINTS['general_corporate'])}. "
        f"{type_instruction} "
        "Строго без текста внутри изображения, без чужих логотипов, без товарных знаков, без водяных знаков. "
        "Не делать полноэкранный фон и не делать широкую фотографию. Нужен маленький визуальный элемент, "
        "пригодный для точечной вставки в слайд. "
        "Стиль: премиальный корпоративный, индустриальный, технологичный, минималистичный. "
        "Палитра: белый, голубой, синий, стальной серый; "
        f"акценты {colors.get('foundation', '#0077C8')}, {colors.get('corporate', '#003D73')}, "
        f"{colors.get('technical', '#66B5E8')}. "
        "Фон прозрачный или очень чистый светлый, композиция компактная, без перегруза мелкими деталями."
    )


def build_image_prompt(slide: dict, deck_plan: dict, brand_config: dict) -> str:
    strategy = detect_slide_asset_strategy(slide, deck_plan)
    return build_png_asset_prompt(slide, deck_plan, brand_config, strategy)


def generate_slide_images(
    project_id: str,
    deck_plan: dict,
    brand_config: dict,
    max_images: int = 5,
) -> list[dict]:
    return generate_slide_png_assets(project_id, deck_plan, brand_config, max_assets=max_images)


def select_slides_for_images(deck_plan: dict, max_images: int = 5) -> list[dict]:
    return select_slides_for_png_assets(deck_plan, max_assets=max_images)


def get_image_mode_for_slide(slide: dict) -> str:
    if slide.get("has_png_assets"):
        return "png-assets"
    return "none"


def _find_category_matches(text: str) -> dict:
    matches = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        found = [keyword for keyword in keywords if keyword.lower() in text]
        if found:
            matches[category] = found
    return matches


def _normalize_layout(slide: dict) -> str:
    slide_type = slide.get("type") or ""
    layout = slide.get("layout") or ""

    if slide_type == "cover" or layout == "hero":
        return "cover"
    if slide_type == "final" or layout == "final":
        return "final"
    if slide_type == "section":
        return "section"
    if layout in {"cards", "impact", "summary"}:
        return "cards"
    if layout == "data" or slide_type == "analytics":
        return "analytics"
    if layout == "timeline" or slide_type == "timeline":
        return "timeline"
    if layout == "risk_matrix" or slide_type == "risks":
        return "risks"
    if layout in {"text", "statement", "bullets", "two_columns", "process"}:
        return "text"
    return "text"
