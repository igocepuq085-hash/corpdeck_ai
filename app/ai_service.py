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

DECK_SYSTEM_PROMPT += """

Строгие правила длины видимого текста:
- title: максимум 55 символов, без двоеточий по возможности, одна короткая мысль.
- subtitle: максимум 90 символов.
- main_fact: максимум 95 символов, одна сильная мысль, не абзац и не канцелярит.
- bullets: максимум 3 пункта, каждый максимум 110 символов.
Не копируй длинные фразы из исходного документа в title/main_fact.
Не помещай весь абзац в main_fact.
Не используй многословные формулировки.
""".strip()

DOCUMENT_CONTEXT_SYSTEM_PROMPT = """
Ты — корпоративный аналитик документов.
Извлеки только проверяемые сведения из исходного текста.
Не выдумывай факты, числа, даты, организации, локации и имена.
Если факт не найден в тексте, оставь поле пустым или массив пустым.
Верни только валидный JSON без markdown.
""".strip()


def analyze_document_context_with_ai(
    extracted_text: str,
    topic: str,
    presentation_type: str,
) -> dict:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY не задан")

    source_text = (extracted_text or "")[:25000]
    prompt = _build_document_context_prompt(source_text, topic, presentation_type)
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = _create_json_response(client, DOCUMENT_CONTEXT_SYSTEM_PROMPT, prompt)
    diagnostics = json.loads(_extract_response_text(response))
    return _normalize_document_diagnostics(diagnostics)


SLIDE_PLAN_SYSTEM_PROMPT = """
Ты — корпоративный архитектор структуры презентаций.
Построй только slide_plan на основе document_context и verified_facts.
Не выдумывай факты, числа, даты, суммы, проценты, организации, локации и KPI.
Используй данные только из verified_facts.
visual_intent не должен содержать чисел, дат, сумм, процентов, KPI, названий станций или мест.
visual_intent должен опираться только на visual_vocabulary и не использовать forbidden_visuals.
Верни только валидный JSON без markdown.
""".strip()


SLIDE_PLAN_SYSTEM_PROMPT = """
Ты — аналитик документов и редактор деловых презентаций.

Твоя задача — внимательно проанализировать текст документа и вернуть строгий JSON со смысловой структурой презентации.

Ты НЕ дизайнер.
Ты НЕ верстальщик.
Ты НЕ создаешь HTML.
Ты НЕ создаешь CSS.
Ты НЕ выбираешь цвета, шрифты, фоны, изображения или расположение блоков.
Ты НЕ описываешь визуальный стиль.

Главная цель — создать краткую, ясную и полезную презентацию, в которую попадут только главные утверждения, проблемы, выводы, показатели, решения, этапы и рекомендации.

Не выдумывай факты, цифры, даты, организации, локации, KPI, экономический эффект или дорожную карту.
Если данных для типа слайда нет, не добавляй этот тип.
Верни только валидный JSON без markdown, комментариев и пояснений.
Все формулировки должны быть на русском языке.
""".strip()


def build_slide_plan_with_ai(
    extracted_text: str,
    topic: str,
    presentation_type: str,
    document_context: dict,
    verified_facts: dict,
    min_slides: int = 10,
) -> dict:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY не задан")

    source_text = (extracted_text or "")[:16000]
    prompt = _build_slide_plan_prompt(
        source_text=source_text,
        topic=topic,
        presentation_type=presentation_type,
        document_context=document_context,
        verified_facts=verified_facts,
        min_slides=min_slides,
    )
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = _create_json_response(client, SLIDE_PLAN_SYSTEM_PROMPT, prompt)
    semantic_plan = json.loads(_extract_response_text(response))
    return _semantic_plan_to_slide_plan(semantic_plan, topic, presentation_type)


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
        bullets = [_trim(str(item), 130) for item in bullets if str(item).strip()][:3]
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


def _build_document_context_prompt(source_text: str, topic: str, presentation_type: str) -> str:
    schema = {
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
    return (
        f"topic: {topic}\n"
        f"presentation_type: {presentation_type}\n\n"
        f"required_json_schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        "Жесткие правила:\n"
        "- Не выдумывай факты.\n"
        "- Не выдумывай числа.\n"
        "- Не выдумывай даты.\n"
        "- Не выдумывай организации.\n"
        "- Не выдумывай локации.\n"
        "- Если факт не найден в тексте, не добавляй его.\n"
        "- confidence укажи от 0 до 1.\n\n"
        f"source_text:\n{source_text}"
    )


def _build_slide_plan_prompt(
    source_text: str,
    topic: str,
    presentation_type: str,
    document_context: dict,
    verified_facts: dict,
    min_slides: int,
) -> str:
    schema = {
        "slide_plan": [
            {
                "slide_no": 1,
                "role": "cover",
                "layout_type": "cover_light",
                "title": "",
                "subtitle": "",
                "message": "",
                "content_blocks": [],
                "data_blocks": [],
                "visual_intent": {
                    "role": "none",
                    "semantic_category": "",
                    "allowed_objects": [],
                    "forbidden_objects": [],
                    "style": "light_premium_corporate",
                    "needs_generation": False,
                    "asset_source": "css_fallback",
                    "data_allowed": False,
                },
                "speaker_note": "",
                "source_fact_ids": [],
            }
        ]
    }
    roles = [
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
    ]
    layouts = [
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
    ]
    return (
        f"topic: {topic}\n"
        f"presentation_type: {presentation_type}\n"
        f"slide_count: минимум {max(10, min_slides)}, максимум 14\n\n"
        f"allowed_roles: {json.dumps(roles, ensure_ascii=False)}\n"
        f"allowed_layout_type: {json.dumps(layouts, ensure_ascii=False)}\n\n"
        f"document_context:\n{json.dumps(document_context or {}, ensure_ascii=False, indent=2)}\n\n"
        f"verified_facts:\n{json.dumps(verified_facts or {}, ensure_ascii=False, indent=2)}\n\n"
        f"required_json_schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        "Жесткие правила:\n"
        "- Первый слайд: role=cover, layout_type=cover_light.\n"
        "- Последний слайд: role=final или conclusion.\n"
        "- title <= 60 символов, subtitle <= 100, message <= 140.\n"
        "- content_blocks максимум 4 на слайд.\n"
        "- data_blocks используй только если данные есть в verified_facts.\n"
        "- Нельзя добавлять числа, даты, суммы, проценты или названия, которых нет в verified_facts.\n"
        "- visual_intent не должен содержать цифры, станции, места, суммы, проценты, даты, KPI.\n"
        "- visual_intent.allowed_objects бери только из document_context.visual_vocabulary, если он не пустой.\n"
        "- Не используй document_context.forbidden_visuals.\n\n"
        f"source_text excerpt:\n{source_text}"
    )


def _build_slide_plan_prompt(
    source_text: str,
    topic: str,
    presentation_type: str,
    document_context: dict,
    verified_facts: dict,
    min_slides: int,
) -> str:
    schema = {
        "title": "Краткое название презентации",
        "subtitle": "Краткое описание сути документа",
        "document_summary": "Резюме документа в 2-3 предложениях",
        "main_claims": ["Главное утверждение"],
        "key_problems": ["Проблема"],
        "slides": [
            {
                "type": "cover",
                "title": "Заголовок слайда",
                "subtitle": "Подзаголовок слайда",
                "main_message": "Одна главная мысль слайда",
                "bullets": [],
                "kpis": [],
                "steps": [],
                "conclusion": "Краткий вывод слайда",
                "semantic_category": "general",
            }
        ],
    }
    allowed_types = ["cover", "problem", "analysis", "kpi", "process", "solution", "economics", "roadmap", "final"]
    allowed_categories = [
        "general",
        "transport",
        "safety",
        "digital",
        "finance",
        "process",
        "education",
        "production",
        "regulation",
    ]
    target_min = max(5, min(int(min_slides or 7), 10))
    return (
        f"topic: {topic}\n"
        f"presentation_type: {presentation_type}\n"
        f"slides: от {target_min} до 10\n\n"
        f"allowed_slide_types: {json.dumps(allowed_types, ensure_ascii=False)}\n"
        f"allowed_semantic_category: {json.dumps(allowed_categories, ensure_ascii=False)}\n\n"
        f"document_context:\n{json.dumps(document_context or {}, ensure_ascii=False, indent=2)}\n\n"
        f"verified_facts:\n{json.dumps(verified_facts or {}, ensure_ascii=False, indent=2)}\n\n"
        f"required_json_schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        "Что извлекать: главную тему, проблему, ключевые утверждения, подтвержденные факты, важные числовые показатели, "
        "причины, последствия, решения, экономические/организационные/производственные выводы, этапы и финальное резюме.\n\n"
        "Что не переносить: номера страниц, колонтитулы, повторяющиеся заголовки, реквизиты, оглавление, длинные формальные фразы, "
        "юридический шум, подписи приложений без данных, повторяющиеся абзацы, мусор PDF, случайные числа без контекста и таблицы целиком.\n\n"
        "Критические правила:\n"
        "- Первый слайд всегда type=cover.\n"
        "- Последний слайд всегда type=final.\n"
        "- Каждый слайд раскрывает одну главную мысль.\n"
        "- title до 55 символов, subtitle до 120, main_message до 120, conclusion до 140.\n"
        "- Не более 3 bullets на слайд, bullet до 120 символов.\n"
        "- kpis добавляй только если важные числа есть в verified_facts.\n"
        "- steps добавляй только если этапы, процесс или дорожная карта есть в документе.\n"
        "- Не создавай искусственные KPI, экономику, сроки или дорожную карту.\n"
        "- Не дублируй одну мысль на разных слайдах.\n"
        "- Не используй канцелярит, если можно сказать проще.\n"
        "- Не добавляй дизайн, HTML, CSS, цвета, фоны, изображения или расположение блоков.\n"
        "- Верни только валидный JSON.\n\n"
        f"source_text:\n{source_text}"
    )


def _semantic_plan_to_slide_plan(plan: dict, topic: str, presentation_type: str) -> dict:
    from app.schemas import normalize_slide_payload

    if not isinstance(plan, dict):
        return {"slide_plan": [], "quality_warnings": ["AI вернул не JSON-объект."]}
    slides = plan.get("slides") if isinstance(plan.get("slides"), list) else []
    slides = slides[:10]
    result = []
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            continue
        slide = normalize_slide_payload(slide)
        slide_type = str(slide.get("type") or "analysis")
        role, layout = _semantic_type_to_role_layout(slide_type, index, len(slides))
        bullets = slide.get("bullets") if isinstance(slide.get("bullets"), list) else []
        steps = slide.get("steps") if isinstance(slide.get("steps"), list) else []
        kpis = slide.get("kpis") if isinstance(slide.get("kpis"), list) else []
        charts = slide.get("charts") if isinstance(slide.get("charts"), list) else []
        tables = slide.get("tables") if isinstance(slide.get("tables"), list) else []
        content_blocks = _semantic_blocks_from_bullets_and_steps(bullets, steps)
        data_blocks = _semantic_data_blocks(kpis)
        category = _normalize_semantic_category(str(slide.get("semantic_category") or slide.get("visual_type") or "general"))
        result.append(
            {
                "slide_no": index,
                "role": role,
                "layout_type": layout,
                "title": _trim(str(slide.get("title") or f"Слайд {index}"), 55),
                "subtitle": _trim(str(slide.get("subtitle") or ""), 120),
                "message": _trim(str(slide.get("main_message") or slide.get("conclusion") or ""), 120),
                "content_blocks": content_blocks,
                "data_blocks": data_blocks,
                "charts": charts,
                "tables": tables if not charts else [],
                "visual_intent": {
                    "role": "none",
                    "semantic_category": category,
                    "allowed_objects": [],
                    "forbidden_objects": [],
                    "style": "light_premium_corporate",
                    "needs_generation": False,
                    "asset_source": "css_fallback",
                    "data_allowed": False,
                },
                "speaker_note": "",
                "source_fact_ids": [],
            }
        )
    if result:
        result[0]["role"] = "cover"
        result[0]["layout_type"] = "cover_light"
        result[-1]["role"] = "final"
        result[-1]["layout_type"] = "final_light"
    return {
        "title": _trim(str(plan.get("title") or topic or ""), 90),
        "subtitle": _trim(str(plan.get("subtitle") or presentation_type or ""), 120),
        "document_summary": _trim(str(plan.get("document_summary") or ""), 500),
        "confidence": str(plan.get("confidence") or "medium"),
        "confidence_note": _trim(str(plan.get("confidence_note") or ""), 240),
        "main_claims": plan.get("main_claims") if isinstance(plan.get("main_claims"), list) else [],
        "key_problems": plan.get("key_problems") if isinstance(plan.get("key_problems"), list) else [],
        "slide_plan": result,
        "quality_warnings": [],
    }


def _semantic_type_to_role_layout(slide_type: str, index: int, total: int) -> tuple[str, str]:
    if index == 1 or slide_type == "cover":
        return "cover", "cover_light"
    if index == total or slide_type == "final":
        return "final", "final_light"
    mapping = {
        "problem": ("problem", "problem_metrics_light"),
        "analysis": ("cause_analysis", "problem_metrics_light"),
        "kpi": ("data_overview", "data_dashboard_light"),
        "process": ("schedule_or_process_analysis", "roadmap_light"),
        "solution": ("solution", "problem_metrics_light"),
        "economics": ("economics", "data_dashboard_light"),
        "roadmap": ("roadmap", "roadmap_light"),
    }
    return mapping.get(slide_type, ("context", "problem_metrics_light"))


def _semantic_blocks_from_bullets_and_steps(bullets: list, steps: list) -> list[dict]:
    blocks = []
    for item in bullets[:3]:
        text = _trim(str(item), 120)
        if text:
            blocks.append({"title": "", "text": text})
    for item in steps[:4]:
        if isinstance(item, dict):
            text = _trim(str(item.get("text") or item.get("title") or ""), 140)
        else:
            text = _trim(str(item), 140)
        if text:
            blocks.append({"title": "", "text": text})
    return blocks[:4]


def _semantic_data_blocks(kpis: list) -> list[dict]:
    result = []
    for item in kpis[:4]:
        if not isinstance(item, dict):
            continue
        value = _trim(str(item.get("value") or ""), 40)
        if not value:
            continue
        result.append(
            {
                "label": _trim(str(item.get("label") or "Показатель"), 80),
                "value": value,
                "unit": "",
                "comment": _trim(str(item.get("note") or ""), 140),
            }
        )
    return result


def _normalize_semantic_category(category: str) -> str:
    allowed = {"general", "transport", "safety", "digital", "finance", "process", "education", "production", "regulation"}
    category = (category or "general").strip()
    return category if category in allowed else "general"


SLIDE_PLAN_SYSTEM_PROMPT = """
You are a document analyst and business presentation editor.

Analyze the extracted document text and return a strict JSON structure for a concise business presentation.

You are NOT a designer.
You are NOT a layout engineer.
You do NOT create HTML.
You do NOT create CSS.
You do NOT choose colors, fonts, backgrounds, images, or block positions.
You do NOT describe visual style.

Your only task is to extract meaning and structure.

Return only important claims, problems, conclusions, metrics, decisions, process steps, solutions, and recommendations that are actually supported by the document.

Do not invent facts, numbers, dates, organizations, locations, KPIs, economics, effects, timelines, or roadmaps.
If the document has no data for a slide type, do not create that slide type.
All visible text values in the JSON must be in Russian.
Return only valid JSON. No markdown. No comments. No explanations.
""".strip()


def _build_slide_plan_prompt(
    source_text: str,
    topic: str,
    presentation_type: str,
    document_context: dict,
    verified_facts: dict,
    min_slides: int,
) -> str:
    schema = {
        "title": "Short presentation title in Russian",
        "subtitle": "Short document essence in Russian",
        "document_summary": "2-3 sentence document summary in Russian",
        "confidence": "high | medium | low",
        "confidence_note": "Short note about source data quality in Russian",
        "main_claims": ["Main claim in Russian"],
        "key_problems": ["Key problem in Russian"],
        "slides": [
            {
                "type": "cover",
                "title": "Slide title in Russian",
                "subtitle": "Slide subtitle in Russian",
                "main_message": "One main slide message in Russian",
                "bullets": [],
                "kpis": [],
                "steps": [],
                "charts": [],
                "tables": [],
                "conclusion": "Short slide conclusion in Russian",
                "visual_type": "abstract",
                "semantic_category": "general",
            }
        ],
    }
    allowed_types = ["cover", "problem", "analysis", "kpi", "process", "solution", "economics", "roadmap", "final"]
    allowed_categories = [
        "general",
        "transport",
        "safety",
        "digital",
        "finance",
        "process",
        "education",
        "production",
        "regulation",
    ]
    target_min = max(5, min(int(min_slides or 5), 10))
    return (
        f"topic: {topic}\n"
        f"presentation_type: {presentation_type}\n"
        f"slide_count: from {target_min} to 10\n\n"
        f"allowed_slide_types: {json.dumps(allowed_types, ensure_ascii=False)}\n"
        f"allowed_semantic_category: {json.dumps(allowed_categories, ensure_ascii=False)}\n\n"
        f"document_context:\n{json.dumps(document_context or {}, ensure_ascii=False, indent=2)}\n\n"
        f"verified_facts:\n{json.dumps(verified_facts or {}, ensure_ascii=False, indent=2)}\n\n"
        f"required_json_schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        "Extract only: main topic, main problem, key claims, verified facts, important metrics, causes, consequences, "
        "solutions, economic/organizational/production conclusions, real steps, and final management summary.\n\n"
        "Do not transfer into slides: page numbers, headers/footers, repeated headings, document requisites, table of contents, "
        "formal legal boilerplate, appendix captions without important data, repeated paragraphs, PDF extraction noise, random numbers without context, or whole tables.\n\n"
        "Rules for metrics, tables, and charts:\n"
        "- Search carefully for numeric indicators, comparisons, dynamics, percentages, amounts, volumes, dates, and quantitative conclusions.\n"
        "- All KPIs, tables, and charts must be based only on data found in the document or verified_facts.\n"
        "- Do not invent values, missing periods, percentages, amounts, years, stations, locations, or organizations.\n"
        "- Do not recalculate indicators unless the formula is explicitly present in the document.\n"
        "- Do not create a chart from unrelated numbers or from a number whose meaning is unclear.\n"
        "- Do not mix different units in one chart series.\n"
        "- KPI cards are for separate important numbers.\n"
        "- Use bar chart only for comparison with at least 2 values and one unit.\n"
        "- Use line chart only for time dynamics with at least 3 points and one unit.\n"
        "- Use donut chart only for parts of one clear whole with at least 2 parts.\n"
        "- Use timeline data only when stages, dates, or a roadmap are present; for MVP prefer steps over timeline charts.\n"
        "- Use table only when the data is important but should not be shown as a chart.\n"
        "- Maximum 1 chart per slide and maximum 1 table per slide.\n"
        "- If a chart is present, do not add a table to the same slide.\n"
        "- Table limit: maximum 5 columns and 6 rows.\n"
        "- If numeric data is weak or unclear, leave charts empty and use text conclusions.\n\n"
        "Chart object format:\n"
        '{"chart_type":"bar|line|donut|timeline","title":"...","labels":["..."],"series":[{"name":"...","values":[1,2]}],"unit":"...","source_note":"Данные извлечены из документа"}\n'
        "Table object format:\n"
        '{"title":"...","columns":["..."],"rows":[["..."]],"source_note":"Данные извлечены из документа"}\n\n'
        "Strict slide rules:\n"
        "- First slide type must be cover.\n"
        "- Last slide type must be final.\n"
        "- One slide equals one main idea.\n"
        "- title <= 55 characters, subtitle <= 120, main_message <= 120, conclusion <= 140.\n"
        "- Maximum 3 bullets per slide, each bullet <= 120 characters.\n"
        "- Add kpis only if important numbers exist in verified_facts.\n"
        "- Add steps only if stages, process, procedure, or roadmap exists in the document.\n"
        "- Do not create fake KPIs, fake economics, fake dates, fake timelines, or fake roadmap.\n"
        "- Do not duplicate the same idea across slides.\n"
        "- Avoid bureaucratic wording when a simpler business phrase is possible.\n"
        "- Do not include design, HTML, CSS, colors, backgrounds, images, or layout positions.\n"
        "- All visible text fields must be in Russian.\n"
        "- Return only valid JSON.\n\n"
        f"source_text:\n{source_text}"
    )


def _normalize_document_diagnostics(value: dict) -> dict:
    if not isinstance(value, dict):
        value = {}
    context = value.get("document_context") if isinstance(value.get("document_context"), dict) else {}
    facts = value.get("verified_facts") if isinstance(value.get("verified_facts"), dict) else {}

    context_defaults = {
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
    }
    fact_defaults = {
        "numbers": [],
        "dates": [],
        "names": [],
        "locations": [],
        "organizations": [],
        "terms": [],
        "claims": [],
    }

    normalized_context = {}
    for key, default in context_defaults.items():
        item = context.get(key, default)
        if isinstance(default, list):
            normalized_context[key] = item if isinstance(item, list) else []
        elif key == "confidence":
            try:
                normalized_context[key] = max(0, min(1, float(item)))
            except (TypeError, ValueError):
                normalized_context[key] = 0
        else:
            normalized_context[key] = str(item or "")

    normalized_facts = {}
    for key, default in fact_defaults.items():
        item = facts.get(key, default)
        normalized_facts[key] = item if isinstance(item, list) else []

    return {"document_context": normalized_context, "verified_facts": normalized_facts}


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
        "Text limits for every slide: title <= 55 chars, subtitle <= 90 chars, "
        "main_fact <= 95 chars, max 3 bullets, each bullet <= 110 chars. "
        "Shorten long source phrases; do not copy full paragraphs into title or main_fact.\n\n"
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
