import json

from openai import OpenAI

from app.config import OPENAI_API_KEY, OPENAI_TEXT_MODEL
from app.deck_service import build_deck_plan_from_analysis, build_draft_deck_plan


ANALYSIS_SYSTEM_PROMPT = """
Ты — корпоративный аналитик и презентационный редактор.
Разбери исходный материал в строгий JSON.
Не выдумывай факты и числа.
Если данных нет, пиши пустые массивы или честные нейтральные формулировки.
Пиши на русском языке.
Верни только валидный JSON без markdown.
""".strip()

DECK_SYSTEM_PROMPT = """
Ты — корпоративный презентационный архитектор уровня совета директоров.
Создай строгий JSON-план презентации из анализа исходника.
Не выдумывай факты и числа.
Один слайд = один главный смысл.
Минимум 10 слайдов, максимум 12.
Используй KPI, графики, таблицы и дорожные карты, если это подтверждено исходником.
Соблюдай брендбук и премиальный UI-дизайн.
Не используй большие фоновые изображения, только точечные PNG-элементы.
Верни только валидный JSON без markdown.
""".strip()


def analyze_source_material_with_ai(
    extracted_text: str,
    topic: str,
    presentation_type: str,
    brand_config: dict,
) -> dict:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY не задан")

    source_text = (extracted_text or "")[:30000]
    prompt = _build_analysis_prompt(source_text, topic, presentation_type, brand_config)
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = _create_json_response(client, ANALYSIS_SYSTEM_PROMPT, prompt)
    analysis = json.loads(_extract_response_text(response))
    return _normalize_source_analysis(analysis, topic)


def generate_deck_plan_with_ai(
    extracted_text: str,
    topic: str,
    presentation_type: str,
    brand_config: dict,
    source_analysis: dict | None = None,
    min_slides: int = 10,
) -> dict | None:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY не задан")

    source_text = (extracted_text or "")[:25000]
    analysis = source_analysis or {}
    prompt = _build_deck_prompt(source_text, topic, presentation_type, brand_config, analysis, min_slides)
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = _create_json_response(client, DECK_SYSTEM_PROMPT, prompt)
    deck_plan = json.loads(_extract_response_text(response))
    return validate_and_normalize_deck_plan(deck_plan, topic, source_analysis=analysis)


def validate_and_normalize_deck_plan(deck_plan: dict, topic: str, source_analysis: dict | None = None) -> dict:
    analysis = source_analysis or {}
    if not isinstance(deck_plan, dict):
        return build_deck_plan_from_analysis(analysis, topic, "Корпоративная презентация")

    slides = deck_plan.get("slides")
    if not isinstance(slides, list) or len(slides) < 3:
        if analysis:
            return build_deck_plan_from_analysis(analysis, topic, str(deck_plan.get("presentation_type") or "Корпоративная презентация"))
        return build_draft_deck_plan("", topic, str(deck_plan.get("presentation_type") or "Корпоративная презентация"))

    clean_topic = _trim(str(deck_plan.get("topic") or topic or analysis.get("main_theme") or "Корпоративная презентация"), 160)
    presentation_type = _trim(str(deck_plan.get("presentation_type") or "Корпоративная презентация"), 120)
    slides = slides[:12]
    if len(slides) < 10:
        fallback = build_deck_plan_from_analysis(analysis, clean_topic, presentation_type)
        slides = slides + fallback["slides"][len(slides):10]

    normalized_slides = []
    image_count = 0
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            slide = {}
        content = slide.get("content") if isinstance(slide.get("content"), dict) else {}
        ui_design = slide.get("ui_design") if isinstance(slide.get("ui_design"), dict) else {}
        composition = ui_design.get("composition") or _composition_from_layout(slide.get("layout"), slide.get("type"), index, len(slides))
        bullets = content.get("bullets") if isinstance(content.get("bullets"), list) else []
        bullets = [_trim(str(item), 140) for item in bullets if str(item).strip()][:4]
        kpi_cards = _normalize_kpi_cards(slide.get("kpi_cards"))
        chart_data = _normalize_chart_data(slide.get("chart_data"))
        table_data = _normalize_table_data(slide.get("table_data"))

        png_required = bool(slide.get("png_assets_required"))
        if png_required and image_count >= 8:
            png_required = False
        if png_required:
            image_count += int((slide.get("png_asset_strategy") or {}).get("count") or 1)

        normalized_slides.append(
            {
                "number": index,
                "type": _trim(str(slide.get("type") or "content"), 40),
                "layout": _trim(str(slide.get("layout") or composition), 40),
                "slide_role": _trim(str(slide.get("slide_role") or composition), 60),
                "title": _trim(str(slide.get("title") or f"Слайд {index}"), 120),
                "subtitle": _trim(str(slide.get("subtitle") or ""), 180),
                "footer": clean_topic,
                "main_message": _trim(str(slide.get("main_message") or slide.get("subtitle") or ""), 220),
                "main_fact": _trim(str(slide.get("main_fact") or slide.get("subtitle") or ""), 180),
                "content": {"bullets": bullets, "speaker_note": _trim(str(content.get("speaker_note") or ""), 300)},
                "kpi_cards": kpi_cards,
                "chart_data": chart_data,
                "table_data": table_data,
                "needs_image": False,
                "needs_table": bool(table_data.get("rows")),
                "needs_chart": chart_data.get("type") != "none",
                "ui_design": {
                    "composition": composition,
                    "density": ui_design.get("density") or "medium",
                    "accent_level": ui_design.get("accent_level") or "medium",
                    "visual_weight": ui_design.get("visual_weight") or "balanced",
                    "primary_block": ui_design.get("primary_block") or "title",
                    "secondary_block": ui_design.get("secondary_block") or "none",
                },
                "png_assets_required": png_required,
                "png_asset_strategy": _normalize_png_strategy(slide.get("png_asset_strategy"), composition, analysis),
                "quality_requirements": {
                    "must_show_numbers": bool((analysis.get("numbers") or [])),
                    "must_have_visual_hierarchy": True,
                    "max_bullets": 4,
                    "avoid_generic_text": True,
                },
            }
        )

    normalized_slides[0]["type"] = "cover"
    normalized_slides[0]["layout"] = "hero"
    normalized_slides[0]["ui_design"]["composition"] = "hero"
    normalized_slides[-1]["type"] = "final"
    normalized_slides[-1]["layout"] = "final"
    normalized_slides[-1]["ui_design"]["composition"] = "decision_card"

    deck_plan["topic"] = clean_topic
    deck_plan["presentation_type"] = presentation_type
    deck_plan["slides"] = normalized_slides
    deck_plan["slide_count"] = len(normalized_slides)
    deck_plan["detected_context"] = _ensure_dict(deck_plan.get("detected_context")) or {
        "main_theme": analysis.get("main_theme") or clean_topic,
        "domain": analysis.get("domain") or "general",
        "audience": analysis.get("audience") or "корпоративная аудитория",
        "tone": analysis.get("tone") or "деловой",
        "source_summary": analysis.get("main_message") or "",
    }
    deck_plan["theme_style"] = _ensure_dict(deck_plan.get("theme_style"))
    deck_plan["generation_rules"] = _ensure_dict(deck_plan.get("generation_rules"))
    deck_plan["generation_rules"].update(
        {
            "footer_text": clean_topic,
            "max_images": 0,
            "use_gradient_background": True,
            "title_on_cover": True,
            "topic_in_footer_on_each_slide": True,
            "use_editable_tables": True,
            "use_editable_charts": True,
        }
    )
    deck_plan["data_candidates"] = _ensure_data_candidates(deck_plan.get("data_candidates"), analysis)
    deck_plan["png_asset_candidates"] = [
        {"slide_number": slide["number"], **slide["png_asset_strategy"]}
        for slide in normalized_slides
        if slide.get("png_assets_required")
    ][:8]
    deck_plan["quality_report"] = _ensure_dict(deck_plan.get("quality_report"))
    return deck_plan


def _build_analysis_prompt(source_text: str, topic: str, presentation_type: str, brand_config: dict) -> str:
    schema = {
        "main_theme": "string",
        "main_message": "string",
        "document_type": "presentation/report/memo/business_case/training/unknown",
        "domain": "finance/production/transport/safety/education/hr/it_digital/marketing/sales/construction/legal_compliance/project_management/general",
        "audience": "string",
        "tone": "string",
        "problem": "string",
        "why_it_matters": "string",
        "proposed_solution": "string",
        "expected_result": "string",
        "management_decision": "string",
        "key_facts": [{"fact": "string", "source_context": "string", "importance": "high/medium/low"}],
        "numbers": [{"value": "string", "unit": "string", "meaning": "string", "recommended_use": "kpi/chart/table/text"}],
        "dates": [],
        "risks": [],
        "causes": [],
        "solutions": [],
        "economic_effects": [],
        "implementation_steps": [],
        "storyline": [{"step": 1, "role": "context/problem/evidence/analysis/solution/economics/roadmap/decision/final", "message": "string"}],
        "visual_strategy": {
            "allowed_categories": [],
            "forbidden_categories": [],
            "preferred_ui_blocks": [],
            "recommended_chart_types": [],
            "recommended_table_types": [],
        },
        "quality_notes": [],
    }
    return (
        f"topic: {topic}\n"
        f"presentation_type: {presentation_type}\n"
        f"brand_config: {json.dumps(brand_config, ensure_ascii=False)}\n\n"
        f"JSON schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        "Правила: извлекай конкретные числа, сроки, факты, причины, риски, эффекты и шаги. Не выдумывай.\n\n"
        f"source_text:\n{source_text}"
    )


def _build_deck_prompt(
    source_text: str,
    topic: str,
    presentation_type: str,
    brand_config: dict,
    source_analysis: dict,
    min_slides: int,
) -> str:
    schema = build_deck_plan_from_analysis(source_analysis, topic, presentation_type, min_slides=min_slides)
    schema["slides"] = [schema["slides"][0]]
    return (
        f"topic: {topic}\n"
        f"presentation_type: {presentation_type}\n"
        f"slides: {max(10, min(min_slides, 12))}-12\n\n"
        f"brand_config:\n{json.dumps(brand_config, ensure_ascii=False, indent=2)}\n\n"
        f"source_analysis:\n{json.dumps(source_analysis, ensure_ascii=False, indent=2)}\n\n"
        f"required JSON shape example:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        "Требования: минимум 3 разных UI-композиции; если есть числа, используй 3-5 в kpi_cards/chart_data/table_data; "
        "если есть implementation_steps, сделай timeline; если есть risks, сделай risks; если есть economic_effects, сделай economics. "
        "Не показывай пустые блоки. Не используй большие фоновые изображения. PNG только как маленькие элементы.\n\n"
        f"source_text excerpt:\n{source_text[:12000]}"
    )


def _create_json_response(client: OpenAI, system_prompt: str, user_prompt: str):
    try:
        return client.responses.create(
            model=OPENAI_TEXT_MODEL,
            input=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            response_format={"type": "json_object"},
        )
    except Exception as error:
        if not _looks_like_format_error(error):
            raise
    try:
        return client.responses.create(
            model=OPENAI_TEXT_MODEL,
            input=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            text={"format": {"type": "json_object"}},
        )
    except Exception as error:
        if not _looks_like_format_error(error):
            raise
    return client.chat.completions.create(
        model=OPENAI_TEXT_MODEL,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        response_format={"type": "json_object"},
    )


def _extract_response_text(response) -> str:
    if getattr(response, "output_text", None):
        return response.output_text
    choices = getattr(response, "choices", None)
    if choices:
        return choices[0].message.content
    parts = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                parts.append(text)
    if parts:
        return "\n".join(parts)
    raise RuntimeError("OpenAI не вернул JSON")


def _looks_like_format_error(error: Exception) -> bool:
    message = str(error).lower()
    return isinstance(error, TypeError) or "response_format" in message or "text.format" in message or "unsupported" in message


def _normalize_source_analysis(analysis: dict, topic: str) -> dict:
    if not isinstance(analysis, dict):
        analysis = {}
    analysis.setdefault("main_theme", topic or "Корпоративная презентация")
    analysis.setdefault("main_message", analysis.get("main_theme"))
    analysis.setdefault("document_type", "unknown")
    analysis.setdefault("domain", "general")
    analysis.setdefault("audience", "корпоративная аудитория")
    analysis.setdefault("tone", "деловой")
    for key in ["key_facts", "numbers", "dates", "risks", "causes", "solutions", "economic_effects", "implementation_steps", "storyline", "quality_notes"]:
        if not isinstance(analysis.get(key), list):
            analysis[key] = []
    if not isinstance(analysis.get("visual_strategy"), dict):
        analysis["visual_strategy"] = {}
    return analysis


def _normalize_kpi_cards(value) -> list:
    cards = value if isinstance(value, list) else []
    result = []
    for card in cards[:4]:
        if not isinstance(card, dict) or not str(card.get("value") or "").strip():
            continue
        result.append(
            {
                "label": _trim(str(card.get("label") or "Показатель"), 70),
                "value": _trim(str(card.get("value") or ""), 24),
                "unit": _trim(str(card.get("unit") or ""), 20),
                "comment": _trim(str(card.get("comment") or ""), 90),
            }
        )
    return result


def _normalize_chart_data(value) -> dict:
    value = value if isinstance(value, dict) else {}
    chart_type = value.get("type") or "none"
    labels = value.get("labels") if isinstance(value.get("labels"), list) else []
    values = value.get("values") if isinstance(value.get("values"), list) else []
    if chart_type == "none" or not values:
        return {"type": "none", "title": "", "labels": [], "values": [], "unit": ""}
    return {
        "type": chart_type if chart_type in {"bar", "line", "donut", "progress", "comparison"} else "bar",
        "title": _trim(str(value.get("title") or "Динамика показателей"), 80),
        "labels": [_trim(str(item), 24) for item in labels[:6]],
        "values": values[:6],
        "unit": _trim(str(value.get("unit") or ""), 20),
    }


def _normalize_table_data(value) -> dict:
    value = value if isinstance(value, dict) else {}
    columns = value.get("columns") if isinstance(value.get("columns"), list) else []
    rows = value.get("rows") if isinstance(value.get("rows"), list) else []
    rows = [row for row in rows if isinstance(row, list) and any(str(cell).strip() for cell in row)][:5]
    if not columns or not rows:
        return {"columns": [], "rows": []}
    return {"columns": [_trim(str(item), 40) for item in columns[:4]], "rows": [[_trim(str(cell), 90) for cell in row[:4]] for row in rows]}


def _normalize_png_strategy(value, composition: str, analysis: dict) -> dict:
    value = value if isinstance(value, dict) else {}
    domain = analysis.get("domain") or "general"
    category = value.get("category") or _category_for_domain(domain)
    return {
        "count": max(0, min(_safe_int(value.get("count"), 3 if composition in {"kpi_wall", "timeline", "risks"} else 1), 5)),
        "type": value.get("type") if value.get("type") in {"icon", "mini_illustration", "thematic_accent", "none"} else "icon",
        "placement": value.get("placement") or ("timeline-node" if composition == "timeline" else "card-header"),
        "category": category,
    }


def _category_for_domain(domain: str) -> str:
    return {
        "finance": "analytics",
        "transport": "infrastructure",
        "safety": "safety",
        "education": "training",
        "it_digital": "digital_control",
        "construction": "industrial_environment",
        "hr": "team",
        "marketing": "analytics",
        "sales": "analytics",
        "project_management": "project_management",
    }.get(domain, "general_corporate")


def _composition_from_layout(layout, slide_type, index: int, total: int) -> str:
    if index == 1 or slide_type == "cover":
        return "hero"
    if index == total or slide_type == "final":
        return "decision_card"
    mapping = {
        "hero": "hero",
        "data": "data_focus",
        "timeline": "timeline",
        "risk_matrix": "risks",
        "cards": "kpi_wall",
        "impact": "economics",
        "summary": "decision_card",
        "final": "decision_card",
    }
    return mapping.get(str(layout or ""), "split_story")


def _ensure_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _ensure_data_candidates(value, analysis: dict) -> dict:
    value = value if isinstance(value, dict) else {}
    return {
        "tables": value.get("tables") if isinstance(value.get("tables"), list) else [],
        "charts": value.get("charts") if isinstance(value.get("charts"), list) else [],
        "dates": value.get("dates") if isinstance(value.get("dates"), list) else analysis.get("dates", []),
        "numbers": value.get("numbers") if isinstance(value.get("numbers"), list) else analysis.get("numbers", []),
    }


def _trim(value: str, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _safe_int(value, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback
