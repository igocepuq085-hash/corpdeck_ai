import json
import re
from uuid import uuid4

from app.config import BASE_DIR, OUTPUT_DIR
from app.schemas import normalize_charts, normalize_tables


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


def build_mvp_deck_plan_from_slide_plan(
    topic: str,
    presentation_type: str,
    slide_plan: dict,
    document_context: dict,
    verified_facts: dict,
) -> dict:
    plan = _ensure_slide_plan_dict(slide_plan)
    slides = plan.get("slide_plan", [])
    clean_topic = topic or (document_context or {}).get("topic") or "Корпоративная презентация"
    clean_type = presentation_type or "Корпоративная презентация"

    deck_plan = {
        "topic": clean_topic,
        "presentation_type": clean_type,
        "slide_count": len(slides),
        "detected_context": {
            "main_theme": (document_context or {}).get("topic") or clean_topic,
            "domain": (document_context or {}).get("domain") or "general",
            "audience": (document_context or {}).get("audience") or "корпоративная аудитория",
            "tone": "деловой",
            "source_summary": (document_context or {}).get("purpose") or (document_context or {}).get("main_result") or "",
        },
        "theme_style": {
            "style_name": "light_premium_corporate",
            "visual_tone": "светлый премиальный корпоративный стиль",
        },
        "generation_rules": {
            "footer_text": clean_topic,
            "use_gradient_background": True,
            "topic_in_footer_on_each_slide": True,
            "use_editable_tables": True,
            "use_editable_charts": True,
            "image_generation_enabled": False,
        },
        "slides": [_legacy_slide_from_plan_item(item, clean_topic) for item in slides],
        "slide_plan": slides,
        "slide_plan_quality_warnings": plan.get("quality_warnings", []),
        "document_context": document_context if isinstance(document_context, dict) else {},
        "verified_facts": verified_facts if isinstance(verified_facts, dict) else {},
        "hero_visual_warnings": [],
        "quality_report": {},
    }
    return prepare_mvp_deck_plan(deck_plan)


def normalize_slide_text(deck_plan: dict) -> dict:
    if not isinstance(deck_plan, dict):
        return deck_plan

    slides = deck_plan.get("slides") if isinstance(deck_plan.get("slides"), list) else []
    warnings = []

    for slide in slides:
        if not isinstance(slide, dict):
            continue

        for field, limit in [("title", 65), ("main_fact", 120)]:
            original = str(slide.get(field) or "")
            shortened = _shorten_without_word_break(original, limit)
            if shortened != original:
                slide[field] = shortened
                warnings.append(f"Слайд {slide.get('number')}: поле {field} сокращено.")

        if "subtitle" in slide:
            slide["subtitle"] = _shorten_without_word_break(str(slide.get("subtitle") or ""), 90)

        content = slide.get("content") if isinstance(slide.get("content"), dict) else {}
        bullets = content.get("bullets") if isinstance(content.get("bullets"), list) else []
        normalized_bullets = []
        for bullet in bullets[:3]:
            original = str(bullet)
            shortened = _shorten_without_word_break(original, 130)
            if shortened != original:
                warnings.append(f"Слайд {slide.get('number')}: тезис сокращен.")
            if shortened.strip():
                normalized_bullets.append(shortened)
        content["bullets"] = normalized_bullets
        slide["content"] = content

    if warnings:
        quality_report = deck_plan.get("quality_report") if isinstance(deck_plan.get("quality_report"), dict) else {}
        existing_warnings = quality_report.get("warnings") if isinstance(quality_report.get("warnings"), list) else []
        quality_report["warnings"] = (existing_warnings + warnings)[:12]
        deck_plan["quality_report"] = quality_report

    return deck_plan


def build_empty_document_diagnostics() -> dict:
    return {
        "document_context": {
            "topic": "",
            "document_type": "",
            "domain": "",
            "organization": "",
            "audience": "",
            "purpose": "",
            "main_problem": "",
            "main_solution": "",
            "main_result": "",
            "key_entities": [],
            "key_metrics": [],
            "key_dates": [],
            "key_locations": [],
            "key_processes": [],
            "visual_vocabulary": [],
            "forbidden_visuals": [],
            "confidence": 0,
        },
        "verified_facts": {
            "numbers": [],
            "dates": [],
            "names": [],
            "locations": [],
            "organizations": [],
            "terms": [],
            "claims": [],
        },
    }


ALLOWED_SLIDE_ROLES = {
    "cover",
    "context",
    "problem",
    "cause_analysis",
    "data_overview",
    "schedule_or_process_analysis",
    "solution",
    "communication_or_regulation",
    "investment_or_resources",
    "economics",
    "roadmap",
    "conclusion",
    "final",
    "appendix",
}

ALLOWED_SLIDE_LAYOUTS = {
    "cover_light",
    "context_light",
    "problem_metrics_light",
    "cause_analysis_light",
    "data_dashboard_light",
    "process_timeline_light",
    "schedule_analysis_light",
    "solution_light",
    "communication_protocol_light",
    "economics_dashboard_light",
    "roadmap_light",
    "conclusion_light",
    "final_light",
    "appendix_light",
}

MVP_SLIDE_LAYOUTS = {
    "cover_light",
    "problem_metrics_light",
    "data_dashboard_light",
    "roadmap_light",
    "final_light",
}


def build_fallback_slide_plan(
    document_context: dict,
    topic: str,
    presentation_type: str,
    min_slides: int = 10,
) -> dict:
    context = document_context if isinstance(document_context, dict) else {}
    base_topic = context.get("topic") or topic or "Корпоративная презентация"
    roles = [
        ("cover", "cover_light", base_topic),
        ("context", "context_light", "Контекст документа"),
        ("problem", "problem_metrics_light", "Проблематика"),
        ("cause_analysis", "cause_analysis_light", "Причины и предпосылки"),
        ("data_overview", "data_dashboard_light", "Подтвержденные данные"),
        ("solution", "solution_light", "Предлагаемое решение"),
        ("roadmap", "roadmap_light", "План действий"),
        ("economics", "economics_dashboard_light", "Ожидаемый результат"),
        ("conclusion", "conclusion_light", "Управленческий вывод"),
        ("final", "final_light", "Следующий шаг"),
    ]
    target = max(5, min(10, int(min_slides or 7)))
    while len(roles) < target:
        roles.insert(-1, ("appendix", "appendix_light", "Дополнительный материал"))

    slides = []
    for index, (role, layout, title) in enumerate(roles[:target], start=1):
        slides.append(
            {
                "slide_no": index,
                "role": role,
                "layout_type": layout,
                "title": title,
                "subtitle": presentation_type or "",
                "message": context.get("purpose") or context.get("main_result") or "",
                "content_blocks": [],
                "data_blocks": [],
                "visual_intent": _safe_visual_intent(),
                "speaker_note": "",
                "source_fact_ids": [],
            }
        )
    return {"slide_plan": slides, "quality_warnings": ["slide_plan создан в локальном fallback-режиме."]}


def validate_slide_roles_and_layouts(slide_plan: dict) -> dict:
    plan = _ensure_slide_plan_dict(slide_plan)
    slides = plan["slide_plan"]
    warnings = _quality_warnings(plan)
    if len(slides) < 5:
        start = len(slides) + 1
        for index in range(start, 6):
            slides.append(
                {
                    "slide_no": index,
                    "role": "appendix",
                    "layout_type": "appendix_light",
                    "title": "Дополнительный материал",
                    "subtitle": "",
                    "message": "",
                    "content_blocks": [],
                    "data_blocks": [],
                    "visual_intent": _safe_visual_intent(),
                    "speaker_note": "",
                    "source_fact_ids": [],
                }
            )
        warnings.append("slide_plan дополнен до 5 слайдов.")

    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            slide = {}
            slides[index - 1] = slide
        role = str(slide.get("role") or "context")
        layout = str(slide.get("layout_type") or "context_light")
        if role not in ALLOWED_SLIDE_ROLES:
            warnings.append(f"slide {index}: неизвестная role заменена на context.")
            role = "context"
        if layout not in ALLOWED_SLIDE_LAYOUTS:
            warnings.append(f"slide {index}: неизвестный layout_type заменен на context_light.")
            layout = "context_light"
        slide["slide_no"] = index
        slide["role"] = role
        slide["layout_type"] = layout

    if slides:
        slides[0]["role"] = "cover"
        slides[0]["layout_type"] = "cover_light"
        if slides[-1].get("role") not in {"final", "conclusion"}:
            slides[-1]["role"] = "final"
            slides[-1]["layout_type"] = "final_light"
            warnings.append("last slide: role/layout_type приведены к final/final_light.")

    plan["quality_warnings"] = warnings
    return plan


def run_text_quality_gate(slide_plan: dict) -> dict:
    plan = _ensure_slide_plan_dict(slide_plan)
    warnings = _quality_warnings(plan)
    for slide in plan["slide_plan"]:
        slide_no = slide.get("slide_no")
        for field, limit in [("title", 60), ("subtitle", 100), ("message", 140)]:
            original = str(slide.get(field) or "")
            shortened = _shorten_without_word_break(original, limit)
            if shortened != original:
                slide[field] = shortened
                warnings.append(f"slide {slide_no}: {field} сокращен до {limit} символов.")

        blocks = slide.get("content_blocks")
        if not isinstance(blocks, list):
            blocks = []
        if len(blocks) > 4:
            slide["content_blocks"] = blocks[:4]
            warnings.append(f"slide {slide_no}: content_blocks сокращены до 4.")
        else:
            slide["content_blocks"] = blocks

    plan["quality_warnings"] = warnings
    return plan


def run_data_quality_gate(slide_plan: dict, verified_facts: dict) -> dict:
    plan = _ensure_slide_plan_dict(slide_plan)
    warnings = _quality_warnings(plan)
    verified = _flatten_verified_values(verified_facts)

    for slide in plan["slide_plan"]:
        blocks = slide.get("data_blocks") if isinstance(slide.get("data_blocks"), list) else []
        clean_blocks = []
        for block in blocks:
            block_text = json.dumps(block, ensure_ascii=False) if isinstance(block, (dict, list)) else str(block)
            if _data_block_has_unverified_value(block_text, verified):
                warnings.append(f"slide {slide.get('slide_no')}: data_block удален из-за неподтвержденных данных.")
                continue
            clean_blocks.append(block)
        slide["data_blocks"] = clean_blocks

        clean_charts = []
        for chart in normalize_charts(slide.get("charts")):
            chart_text = json.dumps(_chart_source_for_quality_gate(chart), ensure_ascii=False)
            if _data_block_has_unverified_value(chart_text, verified):
                warnings.append(f"slide {slide.get('slide_no')}: chart удален из-за неподтвержденных чисел.")
                continue
            clean_charts.append(chart)
        slide["charts"] = clean_charts[:1]

        clean_tables = []
        if not clean_charts:
            for table in normalize_tables(slide.get("tables")):
                table_text = json.dumps(table, ensure_ascii=False)
                if _data_block_has_unverified_value(table_text, verified):
                    warnings.append(f"slide {slide.get('slide_no')}: table удалена из-за неподтвержденных чисел.")
                    continue
                clean_tables.append(table)
        slide["tables"] = clean_tables[:1]

    plan["quality_warnings"] = warnings
    return plan


def run_visual_quality_gate(slide_plan: dict, document_context: dict) -> dict:
    plan = _ensure_slide_plan_dict(slide_plan)
    warnings = _quality_warnings(plan)
    context = document_context if isinstance(document_context, dict) else {}
    vocabulary = {str(item).lower() for item in context.get("visual_vocabulary", []) if str(item).strip()}
    forbidden = {str(item).lower() for item in context.get("forbidden_visuals", []) if str(item).strip()}

    for slide in plan["slide_plan"]:
        intent = slide.get("visual_intent") if isinstance(slide.get("visual_intent"), dict) else {}
        intent_text = json.dumps(intent, ensure_ascii=False).lower()
        allowed_objects = [str(item) for item in intent.get("allowed_objects", []) if str(item).strip()]
        has_forbidden = any(item and item in intent_text for item in forbidden)
        has_data_like = bool(re.search(r"\d|%|₽|руб|млн|тыс|kpi|кпи", intent_text, re.IGNORECASE))
        outside_vocabulary = bool(vocabulary) and any(item.lower() not in vocabulary for item in allowed_objects)

        if has_forbidden or has_data_like or outside_vocabulary:
            slide["visual_intent"] = _safe_visual_intent()
            warnings.append(f"slide {slide.get('slide_no')}: visual_intent заменен на css_fallback.")
        else:
            slide["visual_intent"] = _normalize_visual_intent(intent)

    plan["quality_warnings"] = warnings
    return plan


def attach_visual_assets_to_slide_plan(slide_plan: dict, document_context: dict) -> dict:
    plan = _ensure_slide_plan_dict(slide_plan)
    for slide in plan["slide_plan"]:
        intent = slide.get("visual_intent") if isinstance(slide.get("visual_intent"), dict) else {}
        layout_type = str(slide.get("layout_type") or "")
        try:
            from app.visual_service import select_visual_asset

            asset = select_visual_asset(intent, document_context, layout_type)
        except Exception:
            asset = _visual_asset_fallback(intent)
        slide["visual_asset"] = asset
    return plan


def prepare_mvp_deck_plan(deck_plan: dict) -> dict:
    """Normalize old and new plan shapes into five stable light layouts."""
    if not isinstance(deck_plan, dict):
        return deck_plan

    slides = deck_plan.get("slides") if isinstance(deck_plan.get("slides"), list) else []
    slide_plan = deck_plan.get("slide_plan") if isinstance(deck_plan.get("slide_plan"), list) else []
    if not slide_plan:
        slide_plan = [_slide_to_plan_item(slide, index, len(slides)) for index, slide in enumerate(slides, start=1)]

    total = max(len(slide_plan), len(slides))
    prepared = []
    for index in range(total):
        slide_no = index + 1
        item = dict(slide_plan[index]) if index < len(slide_plan) and isinstance(slide_plan[index], dict) else {}
        slide = slides[index] if index < len(slides) and isinstance(slides[index], dict) else {}
        role = _mvp_role(str(item.get("role") or slide.get("slide_role") or slide.get("type") or "context"), slide_no, total)

        item["slide_no"] = slide_no
        item["role"] = role
        item["title"] = _shorten_without_word_break(
            _first_text(item.get("title"), slide.get("title"), f"Слайд {slide_no}"),
            60,
        )
        item["subtitle"] = _shorten_without_word_break(
            _first_text(item.get("subtitle"), slide.get("subtitle"), slide.get("main_message")),
            100,
        )
        item["message"] = _shorten_without_word_break(
            _first_text(item.get("message"), slide.get("main_fact"), slide.get("main_message"), slide.get("subtitle")),
            105,
        )

        content_blocks = item.get("content_blocks")
        if not isinstance(content_blocks, list) or not content_blocks:
            content = slide.get("content") if isinstance(slide.get("content"), dict) else {}
            content_blocks = content.get("bullets") if isinstance(content.get("bullets"), list) else []
        item["content_blocks"] = _normalize_content_blocks(content_blocks)[:4]

        data_blocks = item.get("data_blocks") if isinstance(item.get("data_blocks"), list) else []
        if not data_blocks:
            data_blocks = _data_blocks_from_slide(slide)
        item["data_blocks"] = _normalize_data_blocks(data_blocks)[:4]
        item["charts"] = normalize_charts(item.get("charts") if isinstance(item.get("charts"), list) else slide.get("charts"))
        if not item["charts"]:
            item["charts"] = _charts_from_legacy_slide(slide)
        item["tables"] = [] if item["charts"] else normalize_tables(item.get("tables") if isinstance(item.get("tables"), list) else slide.get("tables"))
        if not item["tables"] and not item["charts"]:
            item["tables"] = _tables_from_legacy_slide(slide)
        item["layout_type"] = _mvp_layout_type(item, slide, slide_no, total)
        item.pop("generated_visual", None)

        visual_asset = item.get("visual_asset") if isinstance(item.get("visual_asset"), dict) else {}
        if not visual_asset or visual_asset.get("asset_source") == "css_fallback" or visual_asset.get("id") == "css_fallback":
            try:
                from app.visual_service import select_visual_asset

                visual_asset = select_visual_asset(
                    item.get("visual_intent") if isinstance(item.get("visual_intent"), dict) else {},
                    deck_plan.get("document_context") if isinstance(deck_plan.get("document_context"), dict) else {},
                    item.get("layout_type") or "",
                )
            except Exception:
                visual_asset = _visual_asset_fallback(item.get("visual_intent") or {})
        item["visual_asset"] = visual_asset
        prepared.append(item)

    if prepared:
        prepared[0]["role"] = "cover"
        prepared[0]["layout_type"] = "cover_light"
        prepared[-1]["role"] = "final"
        prepared[-1]["layout_type"] = "final_light"

    deck_plan["slide_plan"] = prepared
    deck_plan["slide_count"] = len(prepared) or deck_plan.get("slide_count") or len(slides)

    for index, slide in enumerate(slides):
        if not isinstance(slide, dict) or index >= len(prepared):
            continue
        item = prepared[index]
        slide["layout_type"] = item["layout_type"]
        slide["title"] = item["title"] or slide.get("title") or f"Слайд {index + 1}"
        slide["subtitle"] = item["subtitle"] or slide.get("subtitle") or ""
        slide["main_fact"] = item["message"] or slide.get("main_fact") or ""
        content = slide.get("content") if isinstance(slide.get("content"), dict) else {}
        content["bullets"] = [block["text"] for block in item["content_blocks"][:3] if block.get("text")]
        slide["content"] = content

    return deck_plan


def build_fallback_slide_plan(
    document_context: dict,
    topic: str,
    presentation_type: str,
    min_slides: int = 10,
) -> dict:
    context = document_context if isinstance(document_context, dict) else {}
    base_topic = context.get("topic") or topic or "Корпоративная презентация"
    main_message = context.get("purpose") or context.get("main_result") or context.get("main_problem") or ""
    roles = [
        ("cover", "cover_light", base_topic),
        ("context", "problem_metrics_light", "Контекст документа"),
        ("problem", "problem_metrics_light", "Проблематика"),
        ("data_overview", "data_dashboard_light", "Подтвержденные данные"),
        ("solution", "problem_metrics_light", "Предлагаемый подход"),
        ("roadmap", "roadmap_light", "План действий"),
        ("data_overview", "data_dashboard_light", "Ключевые показатели"),
        ("roadmap", "roadmap_light", "Последовательность работ"),
        ("conclusion", "problem_metrics_light", "Управленческий вывод"),
        ("final", "final_light", "Следующий шаг"),
    ]
    target = max(5, min(10, int(min_slides or 7)))
    while len(roles) < target:
        roles.insert(-1, ("context", "problem_metrics_light", "Дополнительный контекст"))

    slides = []
    for index, (role, layout, title) in enumerate(roles[:target], start=1):
        slides.append(
            {
                "slide_no": index,
                "role": role,
                "layout_type": layout,
                "title": title,
                "subtitle": presentation_type or "",
                "message": main_message,
                "content_blocks": [],
                "data_blocks": [],
                "visual_intent": _safe_visual_intent(),
                "speaker_note": "",
                "source_fact_ids": [],
            }
        )
    return {"slide_plan": slides, "quality_warnings": ["slide_plan создан в локальном fallback-режиме."]}


def assign_premium_layouts(deck_plan: dict) -> dict:
    if not isinstance(deck_plan, dict):
        return deck_plan

    slides = deck_plan.get("slides") if isinstance(deck_plan.get("slides"), list) else []
    last_index = len(slides) - 1

    for index, slide in enumerate(slides):
        if not isinstance(slide, dict):
            continue
        if index == 0:
            slide["layout_type"] = "cover_premium"
            continue
        if index == last_index:
            slide["layout_type"] = "final_summary"
            continue

        text = _slide_search_text(slide)
        has_kpi = bool(slide.get("kpi_cards"))
        chart = slide.get("chart_data") if isinstance(slide.get("chart_data"), dict) else {}
        table = slide.get("table_data") if isinstance(slide.get("table_data"), dict) else {}
        has_chart = bool(chart.get("values")) or chart.get("type") not in {None, "", "none"}
        has_table = bool(table.get("rows"))

        if has_kpi or has_chart or has_table:
            slide["layout_type"] = "kpi_dashboard"
        elif _has_any(text, ["этап", "план", "дорожная карта", "внедрение", "процесс", "сценарий", "срок"]):
            slide["layout_type"] = "process_timeline"
        elif _has_any(text, ["сравнение", "вариант", "решение", "эффект", "было", "стало", "выбор"]):
            slide["layout_type"] = "comparison_decision"
        elif _has_any(text, ["проблем", "потер", "риск", "контекст", "актуальн", "предпосыл"]):
            slide["layout_type"] = "problem_context"
        elif len(text) > 320:
            slide["layout_type"] = "two_column_analysis"
        else:
            slide["layout_type"] = "executive_insight"

    return deck_plan


def strip_experimental_fields(deck_plan: dict) -> dict:
    """Remove legacy image/decor fields from saved MVP deck plans."""
    if not isinstance(deck_plan, dict):
        return deck_plan

    for key in [
        "png_asset_candidates",
        "image_candidates",
        "generated_images",
        "generated_png_assets",
    ]:
        deck_plan.pop(key, None)

    for slide in deck_plan.get("slides") or []:
        if not isinstance(slide, dict):
            continue
        for key in [
            "png_assets_required",
            "png_asset_strategy",
            "png_assets",
            "has_png_assets",
            "decorative_layer",
            "generated_image_path",
            "has_generated_image",
            "generated_image_category",
            "generated_image_scene",
            "generated_image_mode",
        ]:
            slide.pop(key, None)

    return deck_plan


def evaluate_deck_quality(deck_plan: dict, source_analysis: dict | None = None) -> dict:
    slides = deck_plan.get("slides") or []
    analysis = source_analysis or {}
    numbers_found = len(analysis.get("numbers") or deck_plan.get("data_candidates", {}).get("numbers") or [])
    numbers_used = 0
    existing_report = deck_plan.get("quality_report") if isinstance(deck_plan.get("quality_report"), dict) else {}
    warnings = list(existing_report.get("warnings") or []) if isinstance(existing_report.get("warnings"), list) else []
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


def validate_static_paths(deck_plan: dict) -> list[str]:
    warnings = []
    plan = deck_plan if isinstance(deck_plan, dict) else {}
    slide_plan = plan.get("slide_plan") if isinstance(plan.get("slide_plan"), list) else []

    for slide in slide_plan:
        if not isinstance(slide, dict):
            continue
        for field in ["generated_visual", "visual_asset"]:
            asset = slide.get(field) if isinstance(slide.get(field), dict) else {}
            file_path = str(asset.get("file") or "").strip()
            if not file_path:
                continue
            if not file_path.startswith("/static/"):
                warnings.append(f"render: slide {slide.get('slide_no')} {field}.file не начинается с /static/.")
                _disable_visual_asset(asset)
                continue
            local_path = BASE_DIR / file_path.lstrip("/")
            if not local_path.exists():
                warnings.append(f"render: slide {slide.get('slide_no')} файл визуала не найден: {file_path}.")
                _disable_visual_asset(asset)

    return warnings


def final_deck_quality_gate(deck_plan: dict) -> dict:
    plan = deck_plan if isinstance(deck_plan, dict) else {}
    warnings = []
    errors = []
    score = 100

    document_context = plan.get("document_context") if isinstance(plan.get("document_context"), dict) else {}
    verified_facts = plan.get("verified_facts") if isinstance(plan.get("verified_facts"), dict) else {}
    slide_plan = plan.get("slide_plan") if isinstance(plan.get("slide_plan"), list) else []

    if not document_context:
        score -= 20
        warnings.append("context: document_context отсутствует.")
    else:
        for key in ["topic", "domain", "confidence"]:
            if document_context.get(key) in [None, ""]:
                score -= 3
                warnings.append(f"context: document_context.{key} не заполнен.")

    if not verified_facts:
        score -= 20
        warnings.append("data: verified_facts отсутствует.")

    if not slide_plan:
        score -= 15
        errors.append("layout: slide_plan отсутствует.")

    verified_values = _flatten_verified_values(verified_facts)
    org_and_locations = _context_forbidden_terms(document_context)
    generated_visuals_count = 0
    css_fallback_count = 0
    slides_with_data = 0
    slides_with_warnings = set()
    layouts_used = []
    data_issue_count = 0
    prompt_issue_count = 0
    unknown_layout_count = 0
    long_title_count = 0
    long_message_count = 0
    empty_title_count = 0

    path_warnings = validate_static_paths(plan)
    warnings.extend(path_warnings)
    for warning in path_warnings:
        if warning.startswith("render: slide "):
            slide_no = _extract_slide_number(warning)
            if slide_no:
                slides_with_warnings.add(slide_no)

    for index, slide in enumerate(slide_plan, start=1):
        if not isinstance(slide, dict):
            score -= 8
            errors.append(f"layout: slide {index} имеет неверный формат.")
            continue

        slide_no = slide.get("slide_no")
        role = str(slide.get("role") or "")
        layout_type = str(slide.get("layout_type") or "")
        layouts_used.append(layout_type or "unknown")
        title = str(slide.get("title") or "").strip()
        subtitle = str(slide.get("subtitle") or "")
        message = str(slide.get("message") or "")
        content_blocks = slide.get("content_blocks") if isinstance(slide.get("content_blocks"), list) else []
        data_blocks = slide.get("data_blocks") if isinstance(slide.get("data_blocks"), list) else []
        charts = slide.get("charts") if isinstance(slide.get("charts"), list) else []
        tables = slide.get("tables") if isinstance(slide.get("tables"), list) else []

        if slide_no != index:
            warnings.append(f"layout: slide {index} перенумерован или идет не по порядку.")
            slides_with_warnings.add(index)
        if index == 1 and role != "cover":
            errors.append("layout: первый слайд должен иметь role=cover.")
        if index == len(slide_plan) and role not in {"final", "conclusion"}:
            errors.append("layout: последний слайд должен иметь role=final или conclusion.")
        if not role:
            score -= 5
            warnings.append(f"layout: slide {index} без role.")
            slides_with_warnings.add(index)
        if not layout_type or layout_type not in ALLOWED_SLIDE_LAYOUTS:
            unknown_layout_count += 1
            score -= 8
            warnings.append(f"layout: slide {index} имеет неизвестный layout_type.")
            slides_with_warnings.add(index)

        if not title:
            empty_title_count += 1
            score -= 5
            warnings.append(f"text: slide {index} без title.")
            slides_with_warnings.add(index)
        if len(title) > 60:
            long_title_count += 1
            score -= 5
            warnings.append(f"text: slide {index} title длиннее 60 символов.")
            slides_with_warnings.add(index)
        if len(subtitle) > 100:
            score -= 2
            warnings.append(f"text: slide {index} subtitle длиннее 100 символов.")
            slides_with_warnings.add(index)
        if len(message) > 140:
            long_message_count += 1
            score -= 5
            warnings.append(f"text: slide {index} message длиннее 140 символов.")
            slides_with_warnings.add(index)
        if len(content_blocks) > 4:
            score -= 2
            warnings.append(f"text: slide {index} содержит больше 4 content_blocks.")
            slides_with_warnings.add(index)

        if data_blocks or charts or tables:
            slides_with_data += 1
        for block in data_blocks:
            block_text = json.dumps(block, ensure_ascii=False) if isinstance(block, dict) else str(block)
            if _data_block_has_unverified_value(block_text, verified_values):
                data_issue_count += 1
                score -= 10
                warnings.append(f"data: slide {index} содержит неподтвержденные числовые/датированные данные.")
                slides_with_warnings.add(index)

        visual_intent_text = json.dumps(slide.get("visual_intent") or {}, ensure_ascii=False)
        if _visual_text_has_forbidden_data(visual_intent_text, org_and_locations):
            score -= 5
            warnings.append(f"visual: slide {index} visual_intent содержит данные, которых не должно быть в визуале.")
            slides_with_warnings.add(index)

        generated_visual = slide.get("generated_visual") if isinstance(slide.get("generated_visual"), dict) else {}
        visual_asset = slide.get("visual_asset") if isinstance(slide.get("visual_asset"), dict) else {}
        if generated_visual.get("enabled") and generated_visual.get("file"):
            generated_visuals_count += 1
            if layout_type in {"data_dashboard_light", "economics_dashboard_light", "schedule_analysis_light", "process_timeline_light", "roadmap_light", "appendix_light"}:
                score -= 10
                warnings.append(f"visual: slide {index} generated_visual используется на data-heavy layout.")
                slides_with_warnings.add(index)
            prompt = str(generated_visual.get("prompt") or "")
            if _visual_text_has_forbidden_data(prompt, org_and_locations):
                prompt_issue_count += 1
                score -= 10
                warnings.append(f"visual: slide {index} generated_visual.prompt содержит запрещенные данные.")
                slides_with_warnings.add(index)
        elif not (visual_asset.get("enabled") and visual_asset.get("file")):
            css_fallback_count += 1

        if layout_type in {"data_dashboard_light", "economics_dashboard_light"} and not data_blocks:
            warnings.append(f"render: slide {index} data-layout будет использовать текстовый fallback.")
            slides_with_warnings.add(index)
        if not generated_visual.get("file") and not visual_asset.get("file"):
            warnings.append(f"render: slide {index} использует css_fallback для визуального слоя.")

    deck_slides = plan.get("slides") if isinstance(plan.get("slides"), list) else []
    for index, slide in enumerate(deck_slides, start=1):
        content = slide.get("content") if isinstance(slide, dict) and isinstance(slide.get("content"), dict) else {}
        bullets = content.get("bullets") if isinstance(content.get("bullets"), list) else []
        if len(bullets) > 3:
            score -= 5
            warnings.append(f"text: deck slide {index} содержит больше 3 bullets.")
            slides_with_warnings.add(index)

    if generated_visuals_count > 3:
        score -= 5
        warnings.append("visual: generated_visual больше 3 на презентацию.")

    if layouts_used:
        most_common_count = max(layouts_used.count(layout) for layout in set(layouts_used))
        if most_common_count / max(len(layouts_used), 1) > 0.60:
            score -= 5
            warnings.append("layout: один layout используется более чем на 60% слайдов.")

    score = max(0, min(100, score))
    status = "ok" if score >= 85 and not errors else ("warning" if score >= 60 and not errors else "failed")

    return {
        "score": score,
        "status": status,
        "warnings": warnings,
        "errors": errors,
        "metrics": {
            "slides_total": len(slide_plan),
            "layouts_used": sorted(set(layouts_used)),
            "generated_visuals_count": generated_visuals_count,
            "css_fallback_count": css_fallback_count,
            "slides_with_data": slides_with_data,
            "slides_with_warnings": len(slides_with_warnings),
            "data_issue_count": data_issue_count,
            "prompt_issue_count": prompt_issue_count,
            "unknown_layout_count": unknown_layout_count,
            "long_title_count": long_title_count,
            "long_message_count": long_message_count,
            "empty_title_count": empty_title_count,
        },
    }


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


def _first_text(*values) -> str:
    for value in values:
        text = _block_to_text(value)
        if text:
            return text
    return ""


def _block_to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = " ".join(value.split())
        return "" if _is_noise_text(text) else text
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for key in ["text", "content", "message", "fact", "title", "name", "label", "description", "meaning", "comment"]:
            if key in value:
                text = _block_to_text(value.get(key))
                if text:
                    return text
        parts = [_block_to_text(item) for item in value.values()]
        text = " ".join(part for part in parts if part)[:220]
        return "" if _is_noise_text(text) else text
    if isinstance(value, list):
        parts = [_block_to_text(item) for item in value]
        text = " ".join(part for part in parts if part)[:220]
        return "" if _is_noise_text(text) else text
    text = " ".join(str(value).split())
    return "" if _is_noise_text(text) else text


def _normalize_content_blocks(blocks: list) -> list[dict]:
    normalized = []
    for index, block in enumerate(blocks or [], start=1):
        if isinstance(block, dict):
            title = _first_text(block.get("title"), block.get("label"), block.get("name"))
            text = _first_text(block.get("text"), block.get("content"), block.get("message"), block.get("fact"), block)
        else:
            title = ""
            text = _block_to_text(block)
        if not text:
            continue
        normalized.append(
            {
                "title": _shorten_without_word_break(title or f"Факт {index}", 48),
                "text": _shorten_without_word_break(text, 130),
            }
        )
    return normalized


def _normalize_data_blocks(blocks: list) -> list[dict]:
    normalized = []
    for index, block in enumerate(blocks or [], start=1):
        if isinstance(block, dict):
            label = _first_text(block.get("label"), block.get("name"), block.get("title"), block.get("meaning"))
            value = _first_text(block.get("value"), block.get("number"), block.get("metric"))
            unit = _first_text(block.get("unit"))
            comment = _first_text(block.get("comment"), block.get("description"), block.get("meaning"), block.get("content"))
        else:
            text = _block_to_text(block)
            match = re.search(r"\d+(?:[.,]\d+)?", text)
            label = "Показатель"
            value = match.group(0) if match else ""
            unit = ""
            comment = text
        if not any([label, value, comment]):
            continue
        normalized.append(
            {
                "label": _shorten_without_word_break(label or f"Показатель {index}", 54),
                "value": _shorten_without_word_break(value, 32),
                "unit": _shorten_without_word_break(unit, 20),
                "comment": _shorten_without_word_break(comment, 110),
            }
        )
    return normalized


def _data_blocks_from_slide(slide: dict) -> list:
    blocks = []
    for card in slide.get("kpi_cards") or []:
        if isinstance(card, dict):
            blocks.append(card)
    chart = slide.get("chart_data") if isinstance(slide.get("chart_data"), dict) else {}
    labels = chart.get("labels") if isinstance(chart.get("labels"), list) else []
    values = chart.get("values") if isinstance(chart.get("values"), list) else []
    for index, value in enumerate(values[:4]):
        blocks.append(
            {
                "label": labels[index] if index < len(labels) else f"Показатель {index + 1}",
                "value": value,
                "unit": chart.get("unit") or "",
                "comment": chart.get("title") or "",
            }
        )
    table = slide.get("table_data") if isinstance(slide.get("table_data"), dict) else {}
    columns = table.get("columns") if isinstance(table.get("columns"), list) else []
    rows = table.get("rows") if isinstance(table.get("rows"), list) else []
    for row in rows[:4]:
        if isinstance(row, list):
            blocks.append(
                {
                    "label": row[0] if len(row) > 0 else (columns[0] if columns else "Показатель"),
                    "value": row[1] if len(row) > 1 else "",
                    "comment": row[2] if len(row) > 2 else "",
                }
            )
    return blocks


def _charts_from_legacy_slide(slide: dict) -> list[dict]:
    chart = slide.get("chart_data") if isinstance(slide.get("chart_data"), dict) else {}
    chart_type = chart.get("type") or chart.get("chart_type")
    labels = chart.get("labels") if isinstance(chart.get("labels"), list) else []
    values = chart.get("values") if isinstance(chart.get("values"), list) else []
    if not chart_type or chart_type == "none" or not labels or not values:
        return []
    return normalize_charts(
        [
            {
                "chart_type": "bar" if chart_type in {"progress", "comparison"} else chart_type,
                "title": chart.get("title") or "",
                "labels": labels,
                "series": [{"name": chart.get("title") or "Показатель", "values": values}],
                "unit": chart.get("unit") or "",
                "source_note": "Данные извлечены из документа",
            }
        ]
    )


def _tables_from_legacy_slide(slide: dict) -> list[dict]:
    table = slide.get("table_data") if isinstance(slide.get("table_data"), dict) else {}
    if not table:
        return []
    return normalize_tables(
        [
            {
                "title": table.get("title") or "",
                "columns": table.get("columns") if isinstance(table.get("columns"), list) else [],
                "rows": table.get("rows") if isinstance(table.get("rows"), list) else [],
                "source_note": "Данные извлечены из документа",
            }
        ]
    )


def _slide_to_plan_item(slide: dict, index: int, total: int) -> dict:
    slide = slide if isinstance(slide, dict) else {}
    content = slide.get("content") if isinstance(slide.get("content"), dict) else {}
    return {
        "slide_no": index,
        "role": "cover" if index == 1 else ("final" if index == total else slide.get("slide_role") or slide.get("type") or "context"),
        "layout_type": slide.get("layout_type") or "",
        "title": slide.get("title") or f"Слайд {index}",
        "subtitle": slide.get("subtitle") or "",
        "message": slide.get("main_fact") or slide.get("main_message") or "",
        "content_blocks": content.get("bullets") if isinstance(content.get("bullets"), list) else [],
        "data_blocks": _data_blocks_from_slide(slide),
        "charts": normalize_charts(slide.get("charts")) or _charts_from_legacy_slide(slide),
        "tables": normalize_tables(slide.get("tables")) or _tables_from_legacy_slide(slide),
        "visual_intent": _safe_visual_intent(),
        "speaker_note": "",
        "source_fact_ids": [],
    }


def _legacy_slide_from_plan_item(item: dict, topic: str) -> dict:
    item = item if isinstance(item, dict) else {}
    slide_no = int(item.get("slide_no") or 1)
    content_blocks = _normalize_content_blocks(item.get("content_blocks") if isinstance(item.get("content_blocks"), list) else [])
    data_blocks = _normalize_data_blocks(item.get("data_blocks") if isinstance(item.get("data_blocks"), list) else [])
    charts = normalize_charts(item.get("charts"))
    tables = [] if charts else normalize_tables(item.get("tables"))
    kpi_cards = [
        {
            "label": block.get("label", ""),
            "value": block.get("value", ""),
            "unit": block.get("unit", ""),
            "comment": block.get("comment", ""),
        }
        for block in data_blocks[:4]
        if block.get("value") or block.get("comment")
    ]
    return {
        "number": slide_no,
        "type": "cover" if slide_no == 1 else ("final" if item.get("role") == "final" else "content"),
        "layout": item.get("layout_type") or "problem_metrics_light",
        "layout_type": item.get("layout_type") or "problem_metrics_light",
        "slide_role": item.get("role") or "context",
        "title": item.get("title") or f"Слайд {slide_no}",
        "subtitle": item.get("subtitle") or "",
        "footer": topic,
        "main_message": item.get("message") or "",
        "main_fact": item.get("message") or "",
        "content": {"bullets": [block.get("text", "") for block in content_blocks[:3] if block.get("text")]},
        "kpi_cards": kpi_cards,
        "charts": charts,
        "tables": tables,
        "chart_data": _legacy_chart_data(charts),
        "table_data": _legacy_table_data(tables),
        "needs_image": False,
        "needs_table": bool(tables),
        "needs_chart": bool(charts),
    }


def _legacy_chart_data(charts: list[dict]) -> dict:
    chart = charts[0] if charts and isinstance(charts[0], dict) else {}
    if not chart:
        return {"type": "none", "title": "", "labels": [], "values": [], "unit": ""}
    series = chart.get("series") if isinstance(chart.get("series"), list) else []
    first_series = series[0] if series and isinstance(series[0], dict) else {}
    return {
        "type": chart.get("chart_type") or "bar",
        "title": chart.get("title") or "",
        "labels": chart.get("labels") if isinstance(chart.get("labels"), list) else [],
        "values": first_series.get("values") if isinstance(first_series.get("values"), list) else [],
        "unit": chart.get("unit") or "",
    }


def _legacy_table_data(tables: list[dict]) -> dict:
    table = tables[0] if tables and isinstance(tables[0], dict) else {}
    if not table:
        return {"columns": [], "rows": []}
    return {
        "columns": table.get("columns") if isinstance(table.get("columns"), list) else [],
        "rows": table.get("rows") if isinstance(table.get("rows"), list) else [],
    }


def _mvp_role(role: str, slide_no: int, total: int) -> str:
    if slide_no == 1:
        return "cover"
    if slide_no == total:
        return "final"
    return role if role in ALLOWED_SLIDE_ROLES else "context"


def _mvp_layout_type(item: dict, slide: dict, slide_no: int, total: int) -> str:
    if slide_no == 1:
        return "cover_light"
    if slide_no == total:
        return "final_light"
    role = str(item.get("role") or "")
    requested = str(item.get("layout_type") or slide.get("layout_type") or "")
    text = " ".join(
        [
            _block_to_text(item.get("title")),
            _block_to_text(item.get("subtitle")),
            _block_to_text(item.get("message")),
            _block_to_text(item.get("content_blocks")),
        ]
    ).lower()
    data_blocks = item.get("data_blocks") if isinstance(item.get("data_blocks"), list) else []
    charts = item.get("charts") if isinstance(item.get("charts"), list) else []
    tables = item.get("tables") if isinstance(item.get("tables"), list) else []
    has_data = _has_meaningful_data_blocks(data_blocks)
    if requested in MVP_SLIDE_LAYOUTS and requested not in {"cover_light", "final_light"}:
        if requested == "data_dashboard_light" and not (has_data or charts or tables):
            return "problem_metrics_light"
        return requested
    if has_data or charts or tables or role in {"data_overview", "economics", "investment_or_resources"}:
        return "data_dashboard_light"
    if role in {"roadmap", "schedule_or_process_analysis"} or _has_any(text, ["этап", "план", "дорож", "срок", "процесс", "внедрен", "маршрут"]):
        return "roadmap_light"
    return "problem_metrics_light"


def _is_noise_text(text: str) -> bool:
    value = " ".join(str(text or "").split())
    if not value:
        return True
    lower = value.lower()
    noise_markers = [
        "role_group",
        "source_fact_ids",
        "speaker_note",
        "visual_intent",
        "content_blocks",
        "data_blocks",
        "layout_type",
        "slide_no",
    ]
    if any(marker in lower for marker in noise_markers):
        return True
    if lower.startswith("{") or lower.startswith("[") or lower.endswith("}"):
        return True
    if lower.count(":") >= 2 and ("{" in lower or "'" in lower or '"' in lower):
        return True
    if re.search(r"\b(type|content|role|layout|slide|group)\s*[:=]", lower):
        return True
    return False


def _has_meaningful_data_blocks(data_blocks: list[dict]) -> bool:
    meaningful = []
    for block in data_blocks or []:
        if not isinstance(block, dict):
            continue
        value = str(block.get("value") or "").strip()
        unit = str(block.get("unit") or "").strip().lower()
        label = str(block.get("label") or "").strip().lower()
        comment = str(block.get("comment") or "").strip().lower()
        text = " ".join([label, value, unit, comment])
        if not value:
            continue
        if re.fullmatch(r"\d{2,4}[-/]\d{2,4}", value) and any(word in text for word in ["номер", "проект", "id"]):
            continue
        if re.fullmatch(r"\d{1,4}", value) and any(word in text for word in ["слайд", "slide", "номер"]):
            continue
        if unit or re.search(r"%|₽|руб|млн|тыс|км|час|дн|шт|тонн", text, re.IGNORECASE):
            meaningful.append(block)
            continue
        if re.search(r"\d+[.,]\d+", value):
            meaningful.append(block)
            continue
        if len(value) >= 5 and not any(word in text for word in ["номер", "проект", "id"]):
            meaningful.append(block)
    return len(meaningful) >= 2


def _shorten_without_word_break(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    cutoff = max(0, limit - 1)
    shortened = text[:cutoff].rstrip()
    if " " in shortened:
        shortened = shortened.rsplit(" ", 1)[0].rstrip()
    return f"{shortened}…"


def _slide_search_text(slide: dict) -> str:
    content = slide.get("content") if isinstance(slide.get("content"), dict) else {}
    bullets = content.get("bullets") if isinstance(content.get("bullets"), list) else []
    parts = [
        slide.get("title", ""),
        slide.get("subtitle", ""),
        slide.get("main_fact", ""),
        slide.get("main_message", ""),
        " ".join(str(item) for item in bullets),
    ]
    return " ".join(str(item) for item in parts).lower()


def _has_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _ensure_slide_plan_dict(value: dict) -> dict:
    plan = value if isinstance(value, dict) else {}
    slides = plan.get("slide_plan") if isinstance(plan.get("slide_plan"), list) else []
    if len(slides) > 10:
        slides = slides[:10]
    plan["slide_plan"] = slides
    if not isinstance(plan.get("quality_warnings"), list):
        plan["quality_warnings"] = []
    return plan


def _quality_warnings(plan: dict) -> list:
    return list(plan.get("quality_warnings") or []) if isinstance(plan.get("quality_warnings"), list) else []


def _safe_visual_intent() -> dict:
    return {
        "role": "none",
        "semantic_category": "",
        "allowed_objects": [],
        "forbidden_objects": [],
        "style": "light_premium_corporate",
        "needs_generation": False,
        "asset_source": "css_fallback",
        "data_allowed": False,
    }


def _visual_asset_fallback(intent: dict) -> dict:
    intent = intent if isinstance(intent, dict) else {}
    return {
        "id": "css_fallback",
        "enabled": False,
        "semantic_category": str(intent.get("semantic_category") or "neutral"),
        "visual_role": str(intent.get("role") or "support"),
        "file": "",
        "asset_source": "css_fallback",
        "style": "light_premium_corporate",
    }


def _normalize_visual_intent(intent: dict) -> dict:
    safe = _safe_visual_intent()
    if not isinstance(intent, dict):
        return safe
    safe.update(
        {
            "role": str(intent.get("role") or "none"),
            "semantic_category": str(intent.get("semantic_category") or ""),
            "allowed_objects": intent.get("allowed_objects") if isinstance(intent.get("allowed_objects"), list) else [],
            "forbidden_objects": intent.get("forbidden_objects") if isinstance(intent.get("forbidden_objects"), list) else [],
            "style": str(intent.get("style") or "light_premium_corporate"),
            "needs_generation": bool(intent.get("needs_generation")),
            "asset_source": str(intent.get("asset_source") or "css_fallback"),
            "data_allowed": bool(intent.get("data_allowed")),
        }
    )
    return safe


def _flatten_verified_values(verified_facts: dict) -> set[str]:
    facts = verified_facts if isinstance(verified_facts, dict) else {}
    values = set()
    for key in ["numbers", "dates", "names", "locations", "organizations"]:
        items = facts.get(key) if isinstance(facts.get(key), list) else []
        for item in items:
            if isinstance(item, dict):
                values.update(str(value).lower() for value in item.values() if str(value).strip())
            elif str(item).strip():
                values.add(str(item).lower())
    return values


def _data_block_has_unverified_value(text: str, verified_values: set[str]) -> bool:
    lower = text.lower()
    tokens = re.findall(r"\d+(?:[.,]\d+)?\s*(?:%|₽|руб\.?|млн|тыс|г\.?|год|года)?", lower)
    verified_normalized = {_normalize_fact_number_text(value) for value in verified_values if value}
    for token in tokens:
        clean = token.strip()
        normalized = _normalize_fact_number_text(clean)
        if clean and not any(normalized in value or value in normalized for value in verified_normalized):
            return True
    if not verified_values and tokens:
        return True
    return False


def _chart_source_for_quality_gate(chart: dict) -> dict:
    chart = chart if isinstance(chart, dict) else {}
    return {
        "chart_type": chart.get("chart_type"),
        "title": chart.get("title"),
        "labels": chart.get("labels"),
        "series": chart.get("series"),
        "unit": chart.get("unit"),
        "source_note": chart.get("source_note"),
    }


def _normalize_fact_number_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").lower()).replace(",", ".")


def _disable_visual_asset(asset: dict) -> None:
    asset["enabled"] = False
    asset["file"] = ""
    asset["asset_source"] = "css_fallback"


def _context_forbidden_terms(document_context: dict) -> list[str]:
    context = document_context if isinstance(document_context, dict) else {}
    terms = []
    organization = context.get("organization")
    if isinstance(organization, str) and organization.strip():
        terms.append(organization.strip())
    for key in ["key_locations", "key_dates", "key_metrics"]:
        values = context.get(key) if isinstance(context.get(key), list) else []
        terms.extend(str(value).strip() for value in values if str(value).strip())
    return terms


def _visual_text_has_forbidden_data(text: str, forbidden_terms: list[str]) -> bool:
    source = str(text or "")
    lower = source.lower()
    if re.search(r"\d", source) or "%" in source:
        return True
    if re.search(r"\b(?:руб|млн|тыс|км)\b", lower):
        return True
    return any(term and term.lower() in lower for term in forbidden_terms)


def _extract_slide_number(text: str) -> int | None:
    match = re.search(r"slide\s+(\d+)", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None
