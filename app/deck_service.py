import json
import re
from uuid import uuid4

from app.config import OUTPUT_DIR


DOMAIN_KEYWORDS = {
    "finance": ["финанс", "выруч", "прибыл", "затрат", "бюджет", "эконом", "руб", "ebitda", "npv", "irr"],
    "production": ["производ", "завод", "цех", "оборудован", "мощност", "качество", "линия"],
    "transport": ["транспорт", "логист", "маршрут", "перевоз", "вагон", "поезд", "локомотив", "станция"],
    "safety": ["безопас", "охрана труда", "риск", "инцидент", "авар", "сиз", "контроль", "провер"],
    "education": ["обуч", "курс", "тренинг", "компетен", "знани", "навык", "тренаж"],
    "hr": ["hr", "персонал", "сотрудник", "найм", "мотивац", "кадр", "команда"],
    "it_digital": ["цифр", "it", "автоматизац", "систем", "данн", "интеграц", "платформ", "vr"],
    "marketing": ["маркет", "бренд", "аудитор", "кампан", "канал", "позиционир"],
    "sales": ["продаж", "клиент", "воронк", "сделк", "crm", "лид"],
    "construction": ["строител", "объект", "подряд", "смет", "площадк", "проектирован"],
    "legal_compliance": ["регламент", "провер", "комплаенс", "закон", "норматив", "инструкц"],
    "project_management": ["проект", "этап", "срок", "задач", "дорожн", "внедрен", "реализац"],
}

NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s?(?:%|млн|млрд|тыс|руб|₽|км|ч|час|дн|шт|ед|тонн|т)?\b", re.I)
DATE_RE = re.compile(r"\b(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}|[IVX]{1,4}\s?квартал|январь|февраль|март|апрель|май|июнь|июль|август|сентябрь|октябрь|ноябрь|декабрь)\b", re.I)


def build_draft_deck_plan(
    extracted_text: str,
    topic: str,
    presentation_type: str,
    min_slides: int = 10,
) -> dict:
    text = (extracted_text or "").strip()
    clean_topic = (topic or "").strip() or _detect_main_theme(text) or "Корпоративная презентация"
    clean_type = (presentation_type or "Корпоративная презентация").strip()
    source_analysis = build_local_source_analysis(text, clean_topic, clean_type)
    return build_deck_plan_from_analysis(source_analysis, clean_topic, clean_type, min_slides=min_slides)


def build_local_source_analysis(extracted_text: str, topic: str, presentation_type: str) -> dict:
    text = (extracted_text or "").strip()
    compact_text = " ".join(text.split())
    domain = _detect_domain(f"{topic}\n{text}")
    numbers = _extract_numbers(text)
    dates = _extract_dates(text)
    useful_lines = _extract_useful_lines(text)
    key_facts = [
        {
            "fact": line[:220],
            "source_context": line[:300],
            "importance": "high" if index < 3 else "medium",
        }
        for index, line in enumerate(useful_lines[:8])
    ]
    if not key_facts and compact_text:
        key_facts.append(
            {
                "fact": compact_text[:220],
                "source_context": compact_text[:300],
                "importance": "medium",
            }
        )

    risks = _lines_with_keywords(text, ["риск", "угроз", "огранич", "проблем", "опас", "дефицит", "недостат"])
    causes = _lines_with_keywords(text, ["причин", "из-за", "потому", "фактор", "предпосыл"])
    solutions = _lines_with_keywords(text, ["решен", "подход", "предлага", "внедр", "созда", "улучш"])
    effects = _lines_with_keywords(text, ["эффект", "эконом", "рост", "снижен", "результат", "повыш", "сокращ"])
    steps = _lines_with_keywords(text, ["этап", "срок", "план", "дорож", "запуск", "реализац", "мероприят"])

    main_message = _first_non_empty(
        [item.get("fact") for item in key_facts],
        f"Сформировать управленческую логику по теме «{topic}».",
    )

    return {
        "main_theme": topic or "Корпоративная презентация",
        "main_message": main_message,
        "document_type": _detect_document_type(presentation_type, text),
        "domain": domain,
        "audience": _detect_audience(presentation_type),
        "tone": _detect_tone(domain, presentation_type),
        "problem": _first_non_empty(risks, "Требуется уточнить исходную ситуацию и управленческий контекст."),
        "why_it_matters": _first_non_empty(key_facts, "Тема влияет на качество решений, сроки и ожидаемый результат.", key="fact"),
        "proposed_solution": _first_non_empty(solutions, "Сформировать структурированный план действий и критерии результата."),
        "expected_result": _first_non_empty(effects, "Согласованный набор решений, этапов и показателей контроля."),
        "management_decision": "Определить следующий шаг, ответственных и критерии успеха.",
        "key_facts": key_facts,
        "numbers": numbers,
        "dates": dates,
        "risks": risks[:8],
        "causes": causes[:8],
        "solutions": solutions[:8],
        "economic_effects": effects[:8],
        "implementation_steps": steps[:8] or _default_steps(),
        "storyline": _build_storyline(topic, key_facts, risks, solutions, effects),
        "visual_strategy": {
            "allowed_categories": _allowed_visual_categories(domain),
            "forbidden_categories": _forbidden_visual_categories(domain),
            "preferred_ui_blocks": ["kpi_wall", "data_focus", "split_story", "timeline", "decision_card"],
            "recommended_chart_types": ["bar", "progress", "comparison"],
            "recommended_table_types": ["facts", "risks", "roadmap", "economics"],
        },
        "quality_notes": [],
    }


def build_deck_plan_from_analysis(
    source_analysis: dict,
    topic: str,
    presentation_type: str,
    min_slides: int = 10,
) -> dict:
    analysis = source_analysis or {}
    clean_topic = (topic or analysis.get("main_theme") or "Корпоративная презентация").strip()
    slide_count = max(10, min(int(min_slides or 10), 12))
    numbers = analysis.get("numbers") if isinstance(analysis.get("numbers"), list) else []
    key_facts = analysis.get("key_facts") if isinstance(analysis.get("key_facts"), list) else []
    steps = analysis.get("implementation_steps") if isinstance(analysis.get("implementation_steps"), list) else []
    risks = analysis.get("risks") if isinstance(analysis.get("risks"), list) else []
    effects = analysis.get("economic_effects") if isinstance(analysis.get("economic_effects"), list) else []
    causes = analysis.get("causes") if isinstance(analysis.get("causes"), list) else []

    slide_specs = [
        ("cover", "hero", "cover", clean_topic, analysis.get("main_message") or clean_topic, "hero"),
        ("context", "split_story", "context", "Контекст и управленческий смысл", analysis.get("why_it_matters"), "split_story"),
        ("problem", "comparison", "problem", "Исходная ситуация и причины", analysis.get("problem"), "comparison"),
        ("facts", "kpi_wall", "evidence", "Ключевые факты и показатели", _fact_text(key_facts), "kpi_wall"),
        ("analytics", "data_focus", "analysis", "Данные и аналитика", "Числа и факты превращены в управленческие индикаторы.", "data_focus"),
        ("solution", "split_story", "solution", "Предлагаемый подход", analysis.get("proposed_solution"), "split_story"),
        ("roadmap", "timeline", "roadmap", "Дорожная карта", "Этапы реализации и контрольные точки.", "timeline"),
        ("risks", "risks", "risks", "Риски и меры управления", _first_non_empty(risks, "Ключевые ограничения нужно держать в управленческом контуре."), "risks"),
        ("economics", "economics", "economics", "Ожидаемый эффект", analysis.get("expected_result"), "economics"),
        ("final", "decision_card", "decision", "Управленческое решение", analysis.get("management_decision"), "decision_card"),
    ]

    if slide_count > 10:
        slide_specs.insert(5, ("causes", "table_focus", "analysis", "Причины и предпосылки", _first_non_empty(causes, "Причины требуют структурирования и проверки."), "table_focus"))
    if slide_count > 11:
        slide_specs.insert(-1, ("summary", "chart_focus", "decision", "Итоговая модель результата", analysis.get("expected_result"), "chart_focus"))

    slides = []
    for number, (slide_type, layout, role, title, subtitle, composition) in enumerate(slide_specs[:slide_count], start=1):
        slide_numbers = numbers[:4] if composition in {"kpi_wall", "data_focus", "economics", "chart_focus"} else []
        slide_facts = _facts_for_slide(role, analysis)
        kpi_cards = _build_kpi_cards(slide_numbers, fallback_label=title)
        chart_data = _build_chart_data(slide_numbers, title)
        table_data = _build_table_data(role, analysis)
        bullets = _build_bullets(role, analysis)

        if composition == "timeline":
            table_data = {
                "columns": ["Этап", "Содержание", "Статус"],
                "rows": [[str(i + 1), str(step)[:120], "план"] for i, step in enumerate((steps or _default_steps())[:5])],
            }
        if composition == "risks":
            table_data = {
                "columns": ["Риск", "Влияние", "Мера"],
                "rows": [[str(risk)[:90], "среднее", "контроль"] for risk in (risks or bullets)[:5]],
            }

        slides.append(
            {
                "number": number,
                "type": "cover" if number == 1 else ("final" if number == slide_count else slide_type),
                "layout": "hero" if number == 1 else ("final" if number == slide_count else layout),
                "slide_role": role,
                "title": _trim(title or f"Слайд {number}", 120),
                "subtitle": _trim(str(subtitle or ""), 180),
                "footer": clean_topic,
                "main_message": _trim(str(subtitle or title or ""), 220),
                "main_fact": _trim(_first_non_empty(slide_facts, subtitle or title), 180),
                "content": {
                    "bullets": [_trim(str(item), 140) for item in bullets[:4] if str(item).strip()],
                    "speaker_note": _trim(str(subtitle or title or ""), 300),
                },
                "kpi_cards": kpi_cards,
                "chart_data": chart_data,
                "table_data": table_data,
                "needs_image": False,
                "needs_table": bool(table_data.get("rows")),
                "needs_chart": chart_data.get("type") != "none",
                "ui_design": {
                    "composition": composition,
                    "density": "high" if composition in {"data_focus", "table_focus", "risks"} else "medium",
                    "accent_level": "strong" if composition in {"kpi_wall", "economics", "decision_card"} else "medium",
                    "visual_weight": "data" if composition in {"kpi_wall", "data_focus", "economics", "chart_focus"} else "balanced",
                    "primary_block": _primary_block(composition),
                    "secondary_block": _secondary_block(composition),
                },
                "png_assets_required": number not in {1, slide_count} and composition in {"kpi_wall", "data_focus", "timeline", "risks", "split_story"},
                "png_asset_strategy": _png_strategy(composition, analysis.get("domain", "general")),
                "quality_requirements": {
                    "must_show_numbers": bool(numbers),
                    "must_have_visual_hierarchy": True,
                    "max_bullets": 4,
                    "avoid_generic_text": True,
                },
            }
        )

    plan = {
        "topic": clean_topic,
        "presentation_type": presentation_type or "Корпоративная презентация",
        "slide_count": len(slides),
        "detected_context": {
            "main_theme": analysis.get("main_theme") or clean_topic,
            "domain": analysis.get("domain") or "general",
            "audience": analysis.get("audience") or "корпоративная аудитория",
            "tone": analysis.get("tone") or "деловой",
            "source_summary": analysis.get("main_message") or "",
        },
        "theme_style": _theme_style(analysis.get("domain") or "general"),
        "generation_rules": {
            "footer_text": clean_topic,
            "max_images": 0,
            "use_gradient_background": True,
            "title_on_cover": True,
            "topic_in_footer_on_each_slide": True,
            "use_editable_tables": True,
            "use_editable_charts": True,
        },
        "slides": slides,
        "data_candidates": {
            "tables": [slide.get("table_data") for slide in slides if slide.get("table_data", {}).get("rows")],
            "charts": [slide.get("chart_data") for slide in slides if slide.get("chart_data", {}).get("type") != "none"],
            "dates": analysis.get("dates") or [],
            "numbers": analysis.get("numbers") or [],
        },
        "png_asset_candidates": [
            {"slide_number": slide["number"], **slide["png_asset_strategy"]}
            for slide in slides
            if slide.get("png_assets_required")
        ],
        "quality_report": {},
    }
    plan["quality_report"] = evaluate_deck_quality(plan, analysis)
    return plan


def save_deck_plan(deck_plan: dict, project_id: str | None = None) -> str:
    project_id = project_id or uuid4().hex
    project_dir = OUTPUT_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    with (project_dir / "deck_plan.json").open("w", encoding="utf-8") as file:
        json.dump(deck_plan, file, ensure_ascii=False, indent=2)
    return project_id


def load_deck_plan(project_id: str) -> dict:
    plan_path = OUTPUT_DIR / project_id / "deck_plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"План презентации не найден: {project_id}")
    with plan_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def evaluate_deck_quality(deck_plan: dict, source_analysis: dict | None = None) -> dict:
    slides = deck_plan.get("slides") or []
    analysis = source_analysis or {}
    numbers_found = len(analysis.get("numbers") or deck_plan.get("data_candidates", {}).get("numbers") or [])
    numbers_used = 0
    warnings = []
    layout_counts = {}
    generic_slide_count = 0
    empty_visual_blocks = 0
    png_mismatch_count = 0
    slides_with_main_fact = 0
    slides_with_kpi = 0
    slides_with_chart = 0
    slides_with_table = 0

    for slide in slides:
        layout = (slide.get("ui_design") or {}).get("composition") or slide.get("layout") or "default"
        layout_counts[layout] = layout_counts.get(layout, 0) + 1
        bullets = (slide.get("content") or {}).get("bullets") or []
        kpis = slide.get("kpi_cards") or []
        chart = slide.get("chart_data") or {}
        table = slide.get("table_data") or {}
        main_fact = str(slide.get("main_fact") or "").strip()

        if main_fact:
            slides_with_main_fact += 1
        if kpis:
            slides_with_kpi += 1
            numbers_used += len([card for card in kpis if card.get("value")])
        if chart.get("type") and chart.get("type") != "none":
            slides_with_chart += 1
            numbers_used += len(chart.get("values") or [])
        if table.get("rows"):
            slides_with_table += 1

        if len(bullets) > 4:
            warnings.append(f"Слайд {slide.get('number')}: больше 4 тезисов.")
        if not main_fact and not kpis and not chart.get("values"):
            generic_slide_count += 1
        if layout in {"kpi_wall", "data_focus", "chart_focus"} and not (kpis or chart.get("values")):
            empty_visual_blocks += 1
        allowed_png = set(_allowed_visual_categories((analysis or {}).get("domain") or deck_plan.get("detected_context", {}).get("domain") or "general"))
        for asset in slide.get("png_assets") or []:
            if asset.get("category") and asset.get("category") not in allowed_png:
                png_mismatch_count += 1

    if numbers_found and numbers_used == 0:
        warnings.append("В исходном материале есть числа, но они не использованы в KPI или графиках.")
    if len(layout_counts) < 3:
        warnings.append("В презентации меньше 3 разных UI-композиций.")
    if slides_with_main_fact < max(3, len(slides) // 2):
        warnings.append("Слишком мало слайдов с явным главным фактом или смыслом.")

    score = 100
    score -= max(0, len(slides) - slides_with_main_fact) * 4
    score -= generic_slide_count * 6
    score -= empty_visual_blocks * 8
    score -= png_mismatch_count * 5
    if numbers_found and numbers_used < min(numbers_found, 3):
        score -= 15
    if len(layout_counts) < 3:
        score -= 12
    score += min(slides_with_kpi, 3) * 3
    score += min(slides_with_chart, 2) * 4
    score += min(slides_with_table, 2) * 3
    score = max(0, min(score, 100))

    return {
        "score": score,
        "warnings": warnings[:8],
        "metrics": {
            "slides_total": len(slides),
            "slides_with_main_fact": slides_with_main_fact,
            "slides_with_kpi": slides_with_kpi,
            "slides_with_chart": slides_with_chart,
            "slides_with_table": slides_with_table,
            "numbers_found": numbers_found,
            "numbers_used": numbers_used,
            "generic_slide_count": generic_slide_count,
            "empty_visual_blocks": empty_visual_blocks,
            "png_mismatch_count": png_mismatch_count,
        },
    }


def attach_generated_images_to_deck_plan(deck_plan: dict, generated_images: list[dict]) -> dict:
    return deck_plan


def attach_generated_png_assets_to_deck_plan(deck_plan: dict, generated_assets: list[dict]) -> dict:
    assets_by_slide = {}
    for item in generated_assets:
        if item.get("status") == "ok" and item.get("image_path"):
            assets_by_slide.setdefault(item.get("slide_number"), []).append(item)

    for slide in deck_plan.get("slides") or []:
        slide_assets = assets_by_slide.get(slide.get("number"), [])
        slide["png_assets"] = slide_assets
        slide["has_png_assets"] = bool(slide_assets)
        slide["generated_image_path"] = ""
        slide["has_generated_image"] = False

    return deck_plan


def _detect_domain(text: str) -> str:
    lowered = (text or "").lower()
    scores = {domain: sum(1 for keyword in keywords if keyword in lowered) for domain, keywords in DOMAIN_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "general"


def _detect_main_theme(text: str) -> str:
    for line in (text or "").splitlines():
        line = line.strip(" -\t")
        if 12 <= len(line) <= 140 and not line.startswith("---"):
            return line
    return ""


def _detect_document_type(presentation_type: str, text: str) -> str:
    lowered = f"{presentation_type} {text[:1000]}".lower()
    if "обуч" in lowered or "тренинг" in lowered:
        return "training"
    if "отчет" in lowered or "отчёт" in lowered:
        return "report"
    if "business case" in lowered or "инвест" in lowered:
        return "business_case"
    if "поясн" in lowered or "записк" in lowered:
        return "memo"
    if "презентац" in lowered:
        return "presentation"
    return "unknown"


def _detect_audience(presentation_type: str) -> str:
    lowered = (presentation_type or "").lower()
    if "отчет" in lowered or "совет" in lowered:
        return "руководители и владельцы решений"
    if "обуч" in lowered:
        return "сотрудники и участники обучения"
    if "инвест" in lowered or "pitch" in lowered:
        return "инвесторы и партнеры"
    return "корпоративная аудитория"


def _detect_tone(domain: str, presentation_type: str) -> str:
    if domain in {"finance", "project_management"}:
        return "аналитический и управленческий"
    if domain in {"safety", "legal_compliance"}:
        return "строгий и доказательный"
    if domain in {"education", "hr"}:
        return "понятный и практический"
    return "деловой и структурный"


def _extract_numbers(text: str) -> list[dict]:
    results = []
    for match in NUMBER_RE.finditer(text or ""):
        raw = match.group(0).strip()
        value_match = re.match(r"\d+(?:[.,]\d+)?", raw)
        value = value_match.group(0) if value_match else raw
        unit = raw.replace(value, "").strip()
        context = _context_around(text, match.start(), match.end())
        results.append(
            {
                "value": value,
                "unit": unit,
                "meaning": context[:140] or "числовой показатель из исходного материала",
                "recommended_use": "kpi" if len(results) < 4 else "chart",
            }
        )
    return results[:20]


def _extract_dates(text: str) -> list:
    return [{"value": match.group(0), "context": _context_around(text, match.start(), match.end())[:160]} for match in DATE_RE.finditer(text or "")][:12]


def _extract_useful_lines(text: str) -> list:
    keywords = ["цель", "задач", "эффект", "результат", "показатель", "риск", "этап", "решен", "проблем", "вывод"]
    lines = []
    for line in (text or "").splitlines():
        cleaned = " ".join(line.split())
        if len(cleaned) < 20:
            continue
        if any(keyword in cleaned.lower() for keyword in keywords) or NUMBER_RE.search(cleaned):
            lines.append(cleaned)
    return lines[:20]


def _lines_with_keywords(text: str, keywords: list[str]) -> list:
    lines = []
    for line in (text or "").splitlines():
        cleaned = " ".join(line.split())
        if 20 <= len(cleaned) <= 260 and any(keyword in cleaned.lower() for keyword in keywords):
            lines.append(cleaned)
    return lines[:10]


def _context_around(text: str, start: int, end: int) -> str:
    source = text or ""
    left = max(0, start - 80)
    right = min(len(source), end + 100)
    return " ".join(source[left:right].split())


def _first_non_empty(values, fallback: str = "", key: str | None = None) -> str:
    if isinstance(values, list):
        for value in values:
            if isinstance(value, dict) and key:
                value = value.get(key)
            if str(value or "").strip():
                return str(value).strip()
    if isinstance(values, str) and values.strip():
        return values.strip()
    return fallback


def _default_steps() -> list[str]:
    return ["Уточнение исходных данных", "Проработка решения", "Согласование подхода", "Запуск пилота", "Контроль результата"]


def _build_storyline(topic: str, key_facts: list, risks: list, solutions: list, effects: list) -> list:
    return [
        {"step": 1, "role": "context", "message": f"Показать, почему тема «{topic}» важна сейчас."},
        {"step": 2, "role": "evidence", "message": _first_non_empty(key_facts, "Собрать опорные факты.", key="fact")},
        {"step": 3, "role": "analysis", "message": _first_non_empty(risks, "Выделить ограничения и причины.")},
        {"step": 4, "role": "solution", "message": _first_non_empty(solutions, "Сформировать решение и план действий.")},
        {"step": 5, "role": "decision", "message": _first_non_empty(effects, "Зафиксировать ожидаемый эффект и следующий шаг.")},
    ]


def _allowed_visual_categories(domain: str) -> list[str]:
    mapping = {
        "finance": ["analytics", "document_process", "project_management"],
        "transport": ["infrastructure", "rolling_stock", "analytics"],
        "safety": ["safety", "document_process", "industrial_environment"],
        "education": ["training", "digital_control", "document_process"],
        "it_digital": ["digital_control", "analytics", "infrastructure"],
        "construction": ["industrial_environment", "project_management", "document_process"],
        "hr": ["team", "training", "project_management"],
        "marketing": ["analytics", "team", "document_process"],
        "sales": ["analytics", "team", "project_management"],
    }
    return mapping.get(domain, ["general_corporate", "analytics", "project_management"])


def _forbidden_visual_categories(domain: str) -> list[str]:
    if domain != "it_digital" and domain != "education":
        return ["vr_without_context", "random_people", "foreign_logos"]
    return ["random_people", "foreign_logos"]


def _theme_style(domain: str) -> dict:
    style_name = {
        "finance": "Финансово-аналитический",
        "transport": "Инженерный транспортный",
        "safety": "Комплаенс и безопасность",
        "education": "Обучающий корпоративный",
        "it_digital": "Технологичный деловой",
        "project_management": "Проектный отчет",
    }.get(domain, "Корпоративный премиум")
    return {
        "style_name": style_name,
        "gradient": {"type": "linear", "from": "#FFFFFF", "to": "#CFE6F7", "accent": "#0077C8"},
        "visual_tone": "премиальный корпоративный UI-дизайн",
        "image_style": "точечные PNG-акценты без фоновых изображений",
        "chart_style": "чистые CSS-графики в синей палитре",
        "table_style": "компактные таблицы с темно-синей шапкой",
    }


def _fact_text(key_facts: list) -> str:
    return _first_non_empty(key_facts, "Ключевые факты собраны из исходного материала.", key="fact")


def _facts_for_slide(role: str, analysis: dict) -> list:
    mapping = {
        "context": [analysis.get("why_it_matters")],
        "problem": [analysis.get("problem")] + (analysis.get("causes") or []),
        "evidence": [item.get("fact") for item in (analysis.get("key_facts") or [])],
        "analysis": [item.get("meaning") for item in (analysis.get("numbers") or [])],
        "solution": analysis.get("solutions") or [analysis.get("proposed_solution")],
        "roadmap": analysis.get("implementation_steps") or [],
        "risks": analysis.get("risks") or [],
        "economics": analysis.get("economic_effects") or [analysis.get("expected_result")],
        "decision": [analysis.get("management_decision")],
    }
    return [str(item) for item in mapping.get(role, []) if str(item or "").strip()]


def _build_bullets(role: str, analysis: dict) -> list:
    bullets = _facts_for_slide(role, analysis)
    if bullets:
        return bullets[:4]
    return [
        analysis.get("main_message") or "Сформулировать главный вывод.",
        analysis.get("proposed_solution") or "Определить управленческий подход.",
        analysis.get("expected_result") or "Зафиксировать ожидаемый результат.",
    ][:4]


def _build_kpi_cards(numbers: list, fallback_label: str) -> list:
    cards = []
    for item in numbers[:4]:
        cards.append(
            {
                "label": _trim(str(item.get("meaning") or fallback_label), 52),
                "value": str(item.get("value") or ""),
                "unit": str(item.get("unit") or ""),
                "comment": _trim(str(item.get("recommended_use") or "показатель"), 80),
            }
        )
    return cards


def _build_chart_data(numbers: list, title: str) -> dict:
    if len(numbers) < 2:
        return {"type": "none", "title": "", "labels": [], "values": [], "unit": ""}
    values = []
    labels = []
    for index, item in enumerate(numbers[:5], start=1):
        raw = str(item.get("value", "0")).replace(",", ".")
        try:
            values.append(float(raw))
        except ValueError:
            values.append(index * 10)
        labels.append(f"П{index}")
    return {"type": "bar", "title": title, "labels": labels, "values": values, "unit": numbers[0].get("unit", "")}


def _build_table_data(role: str, analysis: dict) -> dict:
    rows = []
    if role == "evidence":
        rows = [[item.get("importance", "medium"), item.get("fact", "")[:120], item.get("source_context", "")[:90]] for item in (analysis.get("key_facts") or [])[:5]]
        return {"columns": ["Важность", "Факт", "Контекст"], "rows": rows}
    if role == "analysis":
        rows = [[item.get("value", ""), item.get("unit", ""), item.get("meaning", "")[:120]] for item in (analysis.get("numbers") or [])[:5]]
        return {"columns": ["Значение", "Ед.", "Смысл"], "rows": rows}
    if role == "economics":
        rows = [["Эффект", str(item)[:140], "оценить"] for item in (analysis.get("economic_effects") or [])[:5]]
        return {"columns": ["Тип", "Описание", "Статус"], "rows": rows}
    return {"columns": [], "rows": []}


def _primary_block(composition: str) -> str:
    return {
        "kpi_wall": "kpi",
        "data_focus": "chart",
        "timeline": "timeline",
        "risks": "table",
        "economics": "kpi",
        "decision_card": "quote",
        "table_focus": "table",
        "chart_focus": "chart",
    }.get(composition, "title")


def _secondary_block(composition: str) -> str:
    return {
        "kpi_wall": "cards",
        "data_focus": "table",
        "split_story": "bullets",
        "comparison": "card",
        "timeline": "cards",
        "risks": "card",
        "economics": "chart",
        "decision_card": "bullets",
    }.get(composition, "none")


def _png_strategy(composition: str, domain: str) -> dict:
    category = _allowed_visual_categories(domain)[0]
    if composition in {"kpi_wall", "data_focus"}:
        return {"count": 3, "type": "icon", "placement": "kpi-row", "category": category}
    if composition == "timeline":
        return {"count": 4, "type": "icon", "placement": "timeline-node", "category": category}
    if composition == "risks":
        return {"count": 3, "type": "icon", "placement": "card-header", "category": "safety" if domain == "safety" else category}
    return {"count": 1, "type": "thematic_accent", "placement": "side-note", "category": category}


def _trim(value: str, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]
