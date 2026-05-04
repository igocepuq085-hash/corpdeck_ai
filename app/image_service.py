import base64
from pathlib import Path

from openai import OpenAI

from app.config import BASE_DIR, OPENAI_API_KEY, OPENAI_IMAGE_MODEL


CATEGORY_KEYWORDS = {
    "infrastructure": ["инфраструктура", "маршрут", "сеть", "логистика", "перевозк", "магистраль", "филиал", "регион"],
    "rolling_stock": ["локомотив", "вагон", "цистерн", "подвижн", "состав", "поезд"],
    "safety": ["безопасность", "охрана труда", "риск", "опасность", "сиз", "высот", "контроль", "проверка"],
    "digital_control": ["цифров", "vr", "тренажер", "технология", "мониторинг", "система", "управление", "диспетчер", "аналитика в реальном времени"],
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
    "infrastructure": "железнодорожная инфраструктура и логистика",
    "rolling_stock": "локомотивы, вагоны и подвижной состав",
    "safety": "промышленная безопасность и контроль надежности",
    "digital_control": "цифровое управление, VR и диспетчеризация",
    "analytics": "чистая бизнес-аналитика и панели мониторинга",
    "training": "обучение персонала и технологическая подготовка",
    "project_management": "управление проектом, этапы и внедрение",
    "team": "корпоративная команда и координация специалистов",
    "industrial_environment": "промышленная площадка и железнодорожный объект",
    "document_process": "регламенты, документы и цифровой документооборот",
    "general_corporate": "универсальный корпоративный индустриально-технологичный фон",
}

CATEGORY_IMAGE_MODES = {
    "analytics": "side-accent",
    "timeline": "side-accent",
    "risks": "side-accent",
    "safety": "full-soft",
    "digital_control": "full-soft",
    "infrastructure": "full-soft",
    "rolling_stock": "full-soft",
    "training": "full-soft",
    "project_management": "side-accent",
    "team": "side-accent",
    "industrial_environment": "full-soft",
    "document_process": "side-accent",
    "general_corporate": "side-accent",
}

CATEGORY_PROMPTS = {
    "infrastructure": "Сюжет: железнодорожная сеть, рельсовая инфраструктура, маршруты, логистические коридоры, северные или промышленные ландшафты. Стиль: чистый корпоративный, широкая перспектива, много воздуха, годится как фон.",
    "rolling_stock": "Сюжет: локомотивы, вагоны, цистерны, подвижной состав, железнодорожная логистика. Стиль: премиальный корпоративный, реалистично, без перегруза, пригодно как фоновый визуал.",
    "safety": "Сюжет: промышленная безопасность, работник в СИЗ, безопасная производственная среда, контроль, защита, надежность. Стиль: деловой, чистый, без драматизации, без травм и аварий.",
    "digital_control": "Сюжет: цифровой контроль, диспетчеризация, VR или цифровая среда, экраны мониторинга, технологии управления. Стиль: технологичный, синие интерфейсные акценты, современная корпоративная эстетика.",
    "analytics": "Сюжет: абстрактная бизнес-аналитика, панели мониторинга, данные, диаграммы как часть окружения. Стиль: очень чисто, мягко, не мешает таблицам и графикам на слайде.",
    "training": "Сюжет: обучение персонала, тренировка, инструктаж, технология обучения. Стиль: корпоративный, человеческий, чистый свет.",
    "project_management": "Сюжет: управление проектом, планирование, координация, визуальная метафора этапов и внедрения. Стиль: деловой, технологичный, не абстрактно-хаотичный.",
    "team": "Сюжет: корпоративная команда, деловое взаимодействие, координация специалистов. Стиль: сдержанный, без стоковой улыбчивой банальности.",
    "industrial_environment": "Сюжет: промышленная площадка, железнодорожный объект, производственная инфраструктура. Стиль: реалистично, чисто, без грязи и перегруза.",
    "document_process": "Сюжет: документы, регламенты, цифровой документооборот, рабочий стол, планшет, инженерная документация. Стиль: нейтральный, аккуратный, корпоративный.",
    "general_corporate": "Сюжет: универсальный корпоративный индустриально-технологичный фон. Стиль: бело-голубой, синие акценты, свободные зоны под текст.",
}


def detect_slide_visual_category(slide: dict, deck_plan: dict) -> dict:
    content = slide.get("content") or {}
    context = deck_plan.get("detected_context") or {}
    local_parts = [
        slide.get("title", ""),
        slide.get("subtitle", ""),
        content.get("speaker_note", ""),
        " ".join(str(item) for item in content.get("bullets") or []),
    ]
    context_parts = [
        context.get("main_theme", ""),
        context.get("domain", ""),
    ]

    matches = _find_category_matches(" ".join(local_parts).lower())
    if not matches:
        matches = _find_category_matches(" ".join(context_parts).lower())

    category = "general_corporate"
    for candidate in CATEGORY_PRIORITY:
        if candidate in matches:
            category = candidate
            break

    image_mode = CATEGORY_IMAGE_MODES.get(category, "side-accent")
    if slide.get("needs_table") and slide.get("needs_chart"):
        image_mode = "side-accent"
    if slide.get("type") in {"analytics", "timeline", "risks"} or slide.get("layout") in {"data", "timeline", "risk_matrix"}:
        image_mode = "side-accent"

    return {
        "category": category,
        "scene": CATEGORY_SCENES[category],
        "keywords": matches.get(category, []),
        "image_mode": image_mode,
    }


def _find_category_matches(text: str) -> dict:
    matches = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        found = [keyword for keyword in keywords if keyword.lower() in text]
        if found:
            matches[category] = found
    return matches


def select_slides_for_images(deck_plan: dict, max_images: int = 5) -> list[dict]:
    slides = deck_plan.get("slides") or []
    if not slides:
        return []

    last_number = slides[-1].get("number")
    allowed_types = {"section", "text", "cards", "analytics", "timeline", "risks"}

    def is_allowed(slide: dict) -> bool:
        return slide.get("number") not in {1, last_number}

    selected = []
    for slide in slides:
        if slide.get("needs_image") and is_allowed(slide):
            selected.append(slide)
        if len(selected) >= max_images:
            return selected[:max_images]

    selected_numbers = {slide.get("number") for slide in selected}
    for slide in slides:
        if slide.get("number") in selected_numbers or not is_allowed(slide):
            continue
        if slide.get("needs_table") and slide.get("needs_chart"):
            continue
        if slide.get("type") in allowed_types or slide.get("layout") in allowed_types:
            selected.append(slide)
        if len(selected) >= max_images:
            break

    return selected[:max_images]


def generate_slide_images(
    project_id: str,
    deck_plan: dict,
    brand_config: dict,
    max_images: int = 5,
) -> list[dict]:
    selected_slides = select_slides_for_images(deck_plan, max_images=max_images)
    if not selected_slides or not OPENAI_API_KEY:
        return []

    output_dir = BASE_DIR / "static" / "generated" / project_id
    output_dir.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=OPENAI_API_KEY)
    results = []

    for slide in selected_slides:
        slide_number = int(slide.get("number") or 0)
        file_name = f"slide_{slide_number:02d}.png"
        local_path = output_dir / file_name
        image_path = f"/static/generated/{project_id}/{file_name}"
        visual_category = detect_slide_visual_category(slide, deck_plan)

        try:
            prompt = build_semantic_image_prompt(slide, deck_plan, brand_config, visual_category)
            response = client.images.generate(
                model=OPENAI_IMAGE_MODEL,
                prompt=prompt,
                size="1536x1024",
                n=1,
            )
            image_data = response.data[0]
            b64_json = getattr(image_data, "b64_json", None)
            if not b64_json:
                raise RuntimeError("OpenAI Image API не вернул изображение в base64")

            local_path.write_bytes(base64.b64decode(b64_json))
            results.append(
                {
                    "slide_number": slide_number,
                    "category": visual_category["category"],
                    "scene": visual_category["scene"],
                    "image_mode": visual_category["image_mode"],
                    "prompt_brief": prompt,
                    "image_path": image_path,
                    "local_path": str(Path("static") / "generated" / project_id / file_name),
                    "status": "ok",
                }
            )
        except Exception as error:
            results.append(
                {
                    "slide_number": slide_number,
                    "category": visual_category["category"],
                    "scene": visual_category["scene"],
                    "image_mode": visual_category["image_mode"],
                    "prompt_brief": build_semantic_image_prompt(slide, deck_plan, brand_config, visual_category),
                    "image_path": "",
                    "local_path": "",
                    "status": "error",
                    "error": str(error),
                }
            )

    return results


def build_image_prompt(slide: dict, deck_plan: dict, brand_config: dict) -> str:
    visual_category = detect_slide_visual_category(slide, deck_plan)
    return build_semantic_image_prompt(slide, deck_plan, brand_config, visual_category)


def build_semantic_image_prompt(
    slide: dict,
    deck_plan: dict,
    brand_config: dict,
    visual_category: dict,
) -> str:
    title = slide.get("title") or deck_plan.get("topic") or "корпоративная презентация"
    subtitle = slide.get("subtitle") or ""
    bullets = (slide.get("content") or {}).get("bullets") or []
    palette = brand_config.get("colors", {})

    return (
        "Фоновое корпоративное изображение для презентации. "
        f"Тема слайда: {title}. "
        f"Контекст слайда: {subtitle}. "
        f"Смысловая категория: {visual_category['category']}. "
        f"Сцена: {visual_category['scene']}. "
        f"Ключевые смыслы: {'; '.join(str(bullet) for bullet in bullets[:3])}. "
        f"{CATEGORY_PROMPTS[visual_category['category']]} "
        "Общие правила: русский визуальный контекст, без текста внутри изображения, без посторонних логотипов, "
        "без товарных знаков, без водяных знаков, без перегруза мелкими деталями, с чистыми зонами под текст. "
        "Фирменная палитра: белый, голубой, синий, стальной серый; "
        f"использовать оттенки {palette.get('foundation', '#0077C8')}, "
        f"{palette.get('corporate', '#003D73')}, {palette.get('technical', '#66B5E8')}. "
        "Стиль: премиальный корпоративный, индустриальный, технологичный. "
        "Изображение пригодно как фон презентационного слайда, не слишком темное, с мягким светом."
    )


def get_image_mode_for_slide(slide: dict) -> str:
    if not slide.get("has_generated_image"):
        return "none"
    return slide.get("generated_image_mode") or detect_slide_visual_category(slide, {})["image_mode"]
