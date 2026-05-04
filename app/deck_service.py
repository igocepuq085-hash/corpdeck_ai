import json
import re
from uuid import uuid4

from app.config import OUTPUT_DIR


DOMAIN_KEYWORDS = {
    "finance": ["финанс", "выручк", "прибыл", "затрат", "бюджет", "ebitda", "маржин"],
    "production": ["производ", "завод", "цех", "оборудован", "мощност", "линия", "качество"],
    "safety": ["безопас", "охрана труда", "инцидент", "риск", "авар", "защит"],
    "education": ["обуч", "курс", "тренинг", "компетенц", "знани", "навык"],
    "strategy": ["стратег", "цель", "рынок", "развит", "инициатив", "приоритет"],
    "investment": ["инвест", "капитал", "окупаем", "npv", "irr", "доходност"],
    "project_management": ["проект", "этап", "срок", "задач", "дорожн", "milestone"],
    "marketing": ["маркет", "бренд", "аудитор", "кампан", "позиционирован"],
    "sales": ["продаж", "клиент", "воронк", "сделк", "crm", "лид"],
    "hr": ["hr", "персонал", "сотрудник", "найм", "мотивац", "кадр"],
    "transport": ["транспорт", "логист", "достав", "маршрут", "перевоз"],
    "construction": ["строител", "объект", "подряд", "смет", "площадк", "проектирован"],
    "it_digital": ["цифров", "it", "автоматизац", "систем", "данн", "интеграц", "платформ"],
    "legal_compliance": ["регламент", "провер", "комплаенс", "закон", "правов", "норматив"],
}

STYLE_BY_DOMAIN = {
    "finance": "Финансово-аналитический",
    "production": "Инженерный промышленный",
    "safety": "Комплаенс и проверка",
    "education": "Обучающий корпоративный",
    "strategy": "Стратегический совет директоров",
    "investment": "Финансово-аналитический",
    "project_management": "Проектный отчет",
    "marketing": "Корпоративный премиум",
    "sales": "Корпоративный премиум",
    "hr": "Обучающий корпоративный",
    "transport": "Инженерный промышленный",
    "construction": "Инженерный промышленный",
    "it_digital": "Технологичный деловой",
    "legal_compliance": "Комплаенс и проверка",
    "general_corporate": "Корпоративный премиум",
}

DATA_KEYWORDS = [
    "показатель",
    "план",
    "факт",
    "срок",
    "задача",
    "этап",
    "бюджет",
    "эффект",
    "результат",
    "количество",
    "динамика",
    "выполнение",
]


def build_draft_deck_plan(
    extracted_text: str,
    topic: str,
    presentation_type: str,
    min_slides: int = 10,
) -> dict:
    text = (extracted_text or "").strip()
    clean_topic = (topic or "").strip()
    clean_type = (presentation_type or "Корпоративная презентация").strip()
    domain = _detect_domain(f"{clean_topic}\n{text}")
    main_theme = clean_topic or _detect_main_theme(text) or "Корпоративная презентация"
    footer = clean_topic or main_theme or "Корпоративная презентация"
    slide_count = max(10, min(min_slides, 12))
    data_candidates = _find_data_candidates(text)

    detected_context = {
        "main_theme": main_theme,
        "domain": domain,
        "audience": _detect_audience(clean_type),
        "tone": _detect_tone(domain, clean_type),
        "source_summary": _summarize_source(text),
    }

    theme_style = _build_theme_style(domain, clean_type)
    generation_rules = {
        "footer_text": footer,
        "max_images": 3,
        "use_gradient_background": True,
        "title_on_cover": True,
        "topic_in_footer_on_each_slide": True,
        "use_editable_tables": True,
        "use_editable_charts": True,
    }

    slides = _build_slides(
        slide_count=slide_count,
        main_theme=main_theme,
        presentation_type=clean_type,
        footer=footer,
        source_summary=detected_context["source_summary"],
        data_candidates=data_candidates,
    )
    image_candidates = _build_image_candidates(slides, main_theme, theme_style)

    return {
        "topic": main_theme,
        "presentation_type": clean_type,
        "slide_count": len(slides),
        "detected_context": detected_context,
        "theme_style": theme_style,
        "generation_rules": generation_rules,
        "slides": slides,
        "data_candidates": data_candidates,
        "image_candidates": image_candidates,
    }


def save_deck_plan(deck_plan: dict, project_id: str | None = None) -> str:
    project_id = project_id or uuid4().hex
    project_dir = OUTPUT_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    plan_path = project_dir / "deck_plan.json"
    with plan_path.open("w", encoding="utf-8") as file:
        json.dump(deck_plan, file, ensure_ascii=False, indent=2)

    return project_id


def load_deck_plan(project_id: str) -> dict:
    plan_path = OUTPUT_DIR / project_id / "deck_plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"План презентации не найден: {project_id}")

    with plan_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _detect_domain(text: str) -> str:
    lowered = text.lower()
    scores = {}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for keyword in keywords if keyword in lowered)

    best_domain = max(scores, key=scores.get)
    if scores[best_domain] == 0:
        return "general_corporate"
    return best_domain


def _detect_main_theme(text: str) -> str:
    for line in text.splitlines():
        line = line.strip(" -\t")
        if 12 <= len(line) <= 140 and not line.startswith("---"):
            return line
    return ""


def _detect_audience(presentation_type: str) -> str:
    lowered = presentation_type.lower()
    if "отчет" in lowered or "совет" in lowered:
        return "руководители и владельцы решений"
    if "обуч" in lowered:
        return "сотрудники и участники обучения"
    if "pitch" in lowered or "инвест" in lowered:
        return "инвесторы и партнеры"
    return "корпоративная аудитория"


def _detect_tone(domain: str, presentation_type: str) -> str:
    lowered = presentation_type.lower()
    if domain in {"finance", "investment"}:
        return "аналитичный и уверенный"
    if domain in {"safety", "legal_compliance"}:
        return "строгий и доказательный"
    if "обуч" in lowered:
        return "понятный и практичный"
    return "деловой и структурный"


def _summarize_source(text: str) -> str:
    if not text:
        return "Исходный текст отсутствует или не был извлечен. План построен по теме презентации."

    sentences = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    summary = " ".join(sentence for sentence in sentences[:3] if sentence)
    return summary[:700]


def _build_theme_style(domain: str, presentation_type: str) -> dict:
    style_name = STYLE_BY_DOMAIN.get(domain, "Корпоративный премиум")

    if "отчет" in presentation_type.lower() and domain == "project_management":
        style_name = "Проектный отчет"

    palette = {
        "finance": ("#eff6ff", "#dbeafe", "#2563eb"),
        "production": ("#f8fafc", "#e2e8f0", "#0f766e"),
        "safety": ("#fff7ed", "#ffedd5", "#ea580c"),
        "education": ("#f0fdf4", "#dcfce7", "#16a34a"),
        "strategy": ("#f8fafc", "#dbeafe", "#1d4ed8"),
        "it_digital": ("#eef2ff", "#e0f2fe", "#4f46e5"),
        "legal_compliance": ("#f8fafc", "#e5e7eb", "#475569"),
    }.get(domain, ("#eef6ff", "#dbeafe", "#2563eb"))

    return {
        "style_name": style_name,
        "gradient": {
            "type": "linear",
            "from": palette[0],
            "to": palette[1],
            "accent": palette[2],
        },
        "visual_tone": "чистый корпоративный дизайн с крупными заголовками",
        "image_style": "реалистичные деловые изображения без логотипов и товарных знаков",
        "chart_style": "простые редактируемые диаграммы с синим акцентом",
        "table_style": "лаконичные редактируемые таблицы с выделением ключевых строк",
    }


def _find_data_candidates(text: str) -> dict:
    numbers = re.findall(r"\b\d+(?:[.,]\d+)?\s?(?:%|млн|млрд|тыс|руб|₽)?\b", text)
    dates = re.findall(
        r"\b(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}|[IVX]{1,4}\s?квартал)\b",
        text,
        flags=re.IGNORECASE,
    )
    useful_lines = []

    for line in text.splitlines():
        cleaned = line.strip()
        lowered = cleaned.lower()
        if cleaned and any(keyword in lowered for keyword in DATA_KEYWORDS):
            useful_lines.append(cleaned[:240])

    tables = []
    if useful_lines:
        tables.append(
            {
                "title": "Структурированные строки из исходного материала",
                "source_lines": useful_lines[:8],
            }
        )

    charts = []
    if len(numbers) >= 3:
        charts.append(
            {
                "title": "Потенциальная диаграмма по числовым значениям",
                "values": numbers[:8],
            }
        )

    return {
        "tables": tables,
        "charts": charts,
        "dates": dates[:12],
        "numbers": numbers[:20],
    }


def _build_slides(
    slide_count: int,
    main_theme: str,
    presentation_type: str,
    footer: str,
    source_summary: str,
    data_candidates: dict,
) -> list:
    has_table_data = bool(data_candidates["tables"] or data_candidates["numbers"])
    has_chart_data = len(data_candidates["numbers"]) >= 3
    fact_bullets = _build_fact_bullets(source_summary, data_candidates)

    base_slides = [
        ("cover", "Титульный слайд", main_theme, "hero", True, False, False, []),
        ("context", "Контекст и актуальность", "Почему тема важна сейчас", "text", False, False, False, fact_bullets[:3]),
        ("goal", "Цель презентации", presentation_type, "statement", False, False, False, [
            "Зафиксировать ключевую логику материала",
            "Показать управленческий контекст",
            "Подготовить основу для решения",
        ]),
        ("problem", "Исходная ситуация и предпосылки", "Что требует внимания", "two_columns", False, False, False, fact_bullets[:3]),
        ("facts", "Ключевые факты из исходного материала", "Опорные наблюдения", "bullets", True, False, False, fact_bullets),
        ("solution", "Предлагаемый подход", "Как можно структурировать дальнейшую работу", "process", False, False, False, [
            "Выделить приоритетные направления",
            "Согласовать критерии результата",
            "Перевести выводы в план действий",
        ]),
        ("analytics", "Данные, показатели или аналитика", "Основа для проверки решений", "data", False, has_table_data, has_chart_data, [
            "Проверить найденные числа и сроки",
            "Собрать показатели в редактируемую таблицу",
            "Использовать график только при достаточном объеме данных",
        ]),
        ("roadmap", "План действий и этапы", "Практическая дорожная карта", "timeline", False, False, False, [
            "Уточнение исходных данных",
            "Проработка решения",
            "Согласование и запуск",
        ]),
        ("risks", "Риски, ограничения и вызовы", "Что может повлиять на результат", "risk_matrix", False, False, False, [
            "Недостаток данных для точной оценки",
            "Ограничения по срокам и ресурсам",
            "Необходимость согласования с участниками",
        ]),
        ("effect", "Ожидаемый эффект и результат", "Какие изменения должны быть достигнуты", "impact", False, False, False, [
            "Более ясная управленческая картина",
            "Согласованный план следующих шагов",
            "Основа для измеримого результата",
        ]),
        ("management", "Управленческие выводы", "Ключевые решения для обсуждения", "summary", False, False, False, [
            "Определить приоритеты",
            "Назначить ответственных",
            "Зафиксировать критерии успеха",
        ]),
        ("final", "Финальный слайд", "Решение и следующий шаг", "final", True, False, False, [
            "Подтвердить направление работы",
            "Согласовать ближайший этап",
            "Подготовить финальную версию презентации",
        ]),
    ]

    if slide_count == 10:
        selected = base_slides[:9] + [
            ("final", "Управленческие выводы и следующий шаг", "Итоговое решение", "final", True, False, False, [
                "Согласовать выводы",
                "Определить ответственных",
                "Запустить следующий этап",
            ])
        ]
    else:
        selected = base_slides[:slide_count]

    slides = []
    for number, item in enumerate(selected, start=1):
        slide_type, title, subtitle, layout, needs_image, needs_table, needs_chart, bullets = item
        slides.append(
            {
                "number": number,
                "type": slide_type,
                "title": title,
                "subtitle": subtitle,
                "layout": layout,
                "footer": footer,
                "needs_image": needs_image,
                "needs_table": needs_table,
                "needs_chart": needs_chart,
                "content": {
                    "bullets": bullets[:5],
                    "speaker_note": _speaker_note(title, main_theme),
                },
            }
        )

    return slides


def _build_fact_bullets(source_summary: str, data_candidates: dict) -> list:
    bullets = []
    if source_summary:
        bullets.append(source_summary[:220])
    if data_candidates["numbers"]:
        bullets.append(f"Найдены числовые значения: {', '.join(data_candidates['numbers'][:5])}")
    if data_candidates["dates"]:
        bullets.append(f"Найдены даты или периоды: {', '.join(data_candidates['dates'][:5])}")
    if not bullets:
        bullets.append("Исходный материал требует дополнительного наполнения фактами.")
    return bullets


def _speaker_note(title: str, main_theme: str) -> str:
    return f"Кратко раскрыть раздел «{title}» в контексте темы «{main_theme}»."


def _build_image_candidates(slides: list, main_theme: str, theme_style: dict) -> list:
    candidates = []

    for slide in slides:
        if slide["needs_image"] and len(candidates) < 3:
            candidates.append(
                {
                    "slide_number": slide["number"],
                    "purpose": slide["type"],
                    "prompt_brief": (
                        f"Деловое корпоративное изображение для слайда «{slide['title']}» "
                        f"по теме «{main_theme}», стиль: {theme_style['style_name']}, "
                        "без логотипов, брендов и товарных знаков."
                    ),
                }
            )

    return candidates


def attach_generated_images_to_deck_plan(deck_plan: dict, generated_images: list[dict]) -> dict:
    image_map = {
        item.get("slide_number"): item
        for item in generated_images
        if item.get("status") == "ok" and item.get("image_path")
    }

    slides = deck_plan.get("slides") or []
    last_number = slides[-1].get("number") if slides else None

    for slide in slides:
        slide_number = slide.get("number")
        image_info = {}
        if slide_number not in {1, last_number}:
            image_info = image_map.get(slide_number, {})

        image_path = image_info.get("image_path", "")
        slide["generated_image_path"] = image_path
        slide["has_generated_image"] = bool(image_path)
        slide["generated_image_category"] = image_info.get("category", "")
        slide["generated_image_scene"] = image_info.get("scene", "")
        slide["generated_image_mode"] = image_info.get("image_mode", "")

    return deck_plan
