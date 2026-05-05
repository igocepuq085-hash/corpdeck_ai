import base64
from pathlib import Path

from openai import OpenAI

from app.config import BASE_DIR, OPENAI_API_KEY, OPENAI_IMAGE_MODEL


CATEGORY_SCENES = {
    "infrastructure": "маршрут, рельсовый узел и логистическая схема",
    "rolling_stock": "лаконичный поезд, вагон или цистерна без логотипов",
    "safety": "щит, каска, чек-лист и контроль безопасности",
    "digital_control": "цифровой интерфейс, мониторинг, сеть и управление",
    "analytics": "график, KPI, панель данных и аналитика",
    "training": "учебный модуль, сценарий и контроль знаний",
    "project_management": "этапы, дорожная карта, координация и внедрение",
    "team": "команда, компетенции и взаимодействие",
    "industrial_environment": "промышленный объект, площадка или инженерная схема",
    "document_process": "документ, регламент, согласование и цифровой документооборот",
    "general_corporate": "универсальный корпоративный технологичный символ",
}

DOMAIN_CATEGORIES = {
    "finance": ["analytics", "document_process", "project_management"],
    "transport": ["infrastructure", "rolling_stock", "analytics"],
    "production": ["industrial_environment", "analytics", "safety"],
    "safety": ["safety", "document_process", "industrial_environment"],
    "education": ["training", "digital_control", "document_process"],
    "it_digital": ["digital_control", "analytics", "infrastructure"],
    "construction": ["industrial_environment", "project_management", "document_process"],
    "hr": ["team", "training", "project_management"],
    "marketing": ["analytics", "team", "document_process"],
    "sales": ["analytics", "project_management", "team"],
    "legal_compliance": ["document_process", "safety", "analytics"],
    "project_management": ["project_management", "analytics", "document_process"],
    "general": ["general_corporate", "analytics", "project_management"],
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
        "keywords": [],
        "image_mode": "png-assets",
    }


def detect_slide_asset_strategy(slide: dict, deck_plan: dict) -> dict:
    context = deck_plan.get("detected_context") or {}
    domain = context.get("domain") or "general"
    requested = slide.get("png_asset_strategy") if isinstance(slide.get("png_asset_strategy"), dict) else {}
    allowed = DOMAIN_CATEGORIES.get(domain, DOMAIN_CATEGORIES["general"])
    requested_category = requested.get("category")
    category = requested_category if requested_category in allowed else allowed[0]

    slide_text = " ".join(
        [
            str(slide.get("title") or ""),
            str(slide.get("subtitle") or ""),
            " ".join(str(item) for item in ((slide.get("content") or {}).get("bullets") or [])),
        ]
    ).lower()
    if "vr" in slide_text or "тренаж" in slide_text:
        category = "digital_control" if domain in {"it_digital", "education", "transport", "general"} else category
    if "безопас" in slide_text or "риск" in slide_text:
        category = "safety" if "safety" in allowed else category
    if "данн" in slide_text or "kpi" in slide_text or "показател" in slide_text:
        category = "analytics" if "analytics" in allowed else category

    composition = (slide.get("ui_design") or {}).get("composition") or slide.get("layout") or "text"
    asset_type = requested.get("type") if requested.get("type") in {"icon", "mini_illustration", "thematic_accent"} else _asset_type_for_composition(composition)
    count = _safe_int(requested.get("count"), _asset_count_for_composition(composition))
    placement = requested.get("placement") or _placement_for_composition(composition)

    return {
        "category": category,
        "scene": CATEGORY_SCENES.get(category, CATEGORY_SCENES["general_corporate"]),
        "keywords": [],
        "recommended_asset_type": asset_type,
        "recommended_count": max(0, min(count, 5)),
        "placement": placement,
        "domain": domain,
    }


def select_slides_for_png_assets(deck_plan: dict, max_assets: int = 8) -> list[dict]:
    slides = deck_plan.get("slides") or []
    if not slides or max_assets <= 0:
        return []

    last_number = slides[-1].get("number")
    preferred = ["kpi_wall", "data_focus", "timeline", "risks", "split_story", "comparison", "economics"]
    selected = []
    planned_assets = 0

    for composition in preferred:
        for slide in slides:
            if slide.get("number") in {1, last_number}:
                continue
            if slide in selected:
                continue
            slide_composition = (slide.get("ui_design") or {}).get("composition") or slide.get("layout")
            if slide_composition != composition:
                continue
            if not slide.get("png_assets_required") and composition not in {"kpi_wall", "timeline", "risks"}:
                continue
            strategy = detect_slide_asset_strategy(slide, deck_plan)
            count = max(1, min(strategy["recommended_count"], max_assets - planned_assets))
            if count <= 0:
                return selected
            selected.append({**slide, "_asset_strategy": {**strategy, "recommended_count": count}})
            planned_assets += count
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
            asset_type = strategy.get("recommended_asset_type", "icon")
            file_part = ASSET_TYPE_FILE_PARTS.get(asset_type, "icon")
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


def build_png_asset_prompt(slide: dict, deck_plan: dict, brand_config: dict, asset_strategy: dict) -> str:
    title = slide.get("title") or deck_plan.get("topic") or "корпоративная презентация"
    domain = asset_strategy.get("domain") or (deck_plan.get("detected_context") or {}).get("domain") or "general"
    category = asset_strategy.get("category") or "general_corporate"
    asset_type = asset_strategy.get("recommended_asset_type") or "icon"
    scene = asset_strategy.get("scene") or CATEGORY_SCENES.get(category, CATEGORY_SCENES["general_corporate"])
    colors = brand_config.get("colors") or {}

    type_text = {
        "icon": "чистая линейная пиктограмма, один объект, квадратная композиция",
        "mini_illustration": "мини-иллюстрация, компактная композиция, один главный объект",
        "thematic_accent": "небольшой тематический акцент, один объект или простая схема",
    }.get(asset_type, "маленький PNG-элемент")

    restrictions = _domain_restrictions(domain)
    return (
        "Создай маленький PNG-элемент для корпоративного слайда. "
        f"Тема слайда: {title}. Домен: {domain}. Категория: {category}. Сюжет: {scene}. "
        f"Тип: {type_text}. "
        "Строго без текста внутри изображения, без логотипов, без товарных знаков, без водяных знаков. "
        "Не делать фотографию на весь слайд, фон, пейзаж или сложную сцену. "
        "Нужен один релевантный объект для точечной вставки в UI-композицию слайда. "
        "Предпочтительно прозрачный фон или очень чистый светлый фон. "
        "Стиль: премиальный корпоративный линейный стиль, минимализм, бело-голубая палитра, синие и стальные акценты. "
        f"Использовать цвета {colors.get('foundation', '#0077C8')}, {colors.get('corporate', '#003D73')}, {colors.get('technical', '#66B5E8')}. "
        f"{restrictions}"
    )


def build_image_prompt(slide: dict, deck_plan: dict, brand_config: dict) -> str:
    strategy = detect_slide_asset_strategy(slide, deck_plan)
    return build_png_asset_prompt(slide, deck_plan, brand_config, strategy)


def generate_slide_images(project_id: str, deck_plan: dict, brand_config: dict, max_images: int = 5) -> list[dict]:
    return generate_slide_png_assets(project_id, deck_plan, brand_config, max_assets=max_images)


def select_slides_for_images(deck_plan: dict, max_images: int = 5) -> list[dict]:
    return select_slides_for_png_assets(deck_plan, max_assets=max_images)


def get_image_mode_for_slide(slide: dict) -> str:
    return "png-assets" if slide.get("has_png_assets") else "none"


def _asset_type_for_composition(composition: str) -> str:
    if composition in {"kpi_wall", "data_focus", "timeline", "risks"}:
        return "icon"
    if composition in {"split_story", "comparison", "economics"}:
        return "thematic_accent"
    return "mini_illustration"


def _asset_count_for_composition(composition: str) -> int:
    return {"timeline": 4, "kpi_wall": 3, "data_focus": 3, "risks": 3}.get(composition, 1)


def _placement_for_composition(composition: str) -> str:
    return {
        "timeline": "timeline-node",
        "kpi_wall": "kpi-row",
        "data_focus": "chart-corner",
        "risks": "card-header",
        "comparison": "side-note",
        "economics": "chart-corner",
    }.get(composition, "side-note")


def _domain_restrictions(domain: str) -> str:
    if domain not in {"it_digital", "education", "transport", "general"}:
        return "Не использовать VR, если это явно не указано в теме. "
    if domain not in {"hr", "education", "team"}:
        return "Не изображать людей, если это не требуется смыслом. "
    return ""


def _safe_int(value, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback
