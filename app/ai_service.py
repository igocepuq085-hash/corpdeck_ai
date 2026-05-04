import json

from openai import OpenAI

from app.config import OPENAI_API_KEY, OPENAI_TEXT_MODEL
from app.deck_service import build_draft_deck_plan


SYSTEM_PROMPT = """
Ты — корпоративный презентационный архитектор.
Твоя задача — из исходного текста создать строгий JSON-план презентации.
Не выдумывай факты.
Не добавляй данные, которых нет в исходнике.
Пиши на русском языке.
Один слайд = один главный смысл.
Минимум 10 слайдов, максимум 12.
Соблюдай брендбук.
Верни только валидный JSON без markdown.
""".strip()


def generate_deck_plan_with_ai(
    extracted_text: str,
    topic: str,
    presentation_type: str,
    brand_config: dict,
    min_slides: int = 10,
) -> dict | None:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY не задан")

    source_text = (extracted_text or "")[:25000]
    client = OpenAI(api_key=OPENAI_API_KEY)
    user_prompt = _build_user_prompt(
        source_text=source_text,
        topic=topic,
        presentation_type=presentation_type,
        brand_config=brand_config,
        min_slides=min_slides,
    )

    response = _create_json_response(client, user_prompt)
    raw_text = _extract_response_text(response)
    deck_plan = json.loads(raw_text)
    return validate_and_normalize_deck_plan(deck_plan, topic or "Корпоративная презентация")


def validate_and_normalize_deck_plan(deck_plan: dict, topic: str) -> dict:
    if not isinstance(deck_plan, dict):
        return build_draft_deck_plan("", topic, "Корпоративная презентация")

    slides = deck_plan.get("slides")
    if not isinstance(slides, list) or len(slides) < 3:
        return build_draft_deck_plan(
            "",
            topic,
            str(deck_plan.get("presentation_type") or "Корпоративная презентация"),
        )

    clean_topic = _trim(str(deck_plan.get("topic") or topic or "Корпоративная презентация"), 160)
    slides = slides[:12]

    if len(slides) < 10:
        fallback = build_draft_deck_plan(
            "",
            clean_topic,
            str(deck_plan.get("presentation_type") or "Корпоративная презентация"),
        )
        slides = slides + fallback["slides"][len(slides):10]

    image_count = 0
    normalized_slides = []
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            slide = {}

        content = slide.get("content") if isinstance(slide.get("content"), dict) else {}
        bullets = content.get("bullets") if isinstance(content.get("bullets"), list) else []
        bullets = [_trim(str(bullet), 140) for bullet in bullets[:5] if str(bullet).strip()]

        needs_image = bool(slide.get("needs_image"))
        if needs_image and image_count >= 3:
            needs_image = False
        if needs_image:
            image_count += 1

        normalized_slides.append(
            {
                "number": index,
                "type": _trim(str(slide.get("type") or "content"), 40),
                "title": _trim(str(slide.get("title") or f"Слайд {index}"), 120),
                "subtitle": _trim(str(slide.get("subtitle") or ""), 180),
                "layout": _trim(str(slide.get("layout") or "text"), 40),
                "footer": clean_topic,
                "needs_image": needs_image,
                "needs_table": bool(slide.get("needs_table")),
                "needs_chart": bool(slide.get("needs_chart")),
                "content": {
                    "bullets": bullets,
                    "speaker_note": _trim(str(content.get("speaker_note") or ""), 300),
                },
            }
        )

    normalized_slides[0]["type"] = "cover"
    normalized_slides[0]["layout"] = "hero"
    normalized_slides[-1]["type"] = "final"
    normalized_slides[-1]["layout"] = "final"

    deck_plan["topic"] = clean_topic
    deck_plan["presentation_type"] = _trim(
        str(deck_plan.get("presentation_type") or "Корпоративная презентация"),
        120,
    )
    deck_plan["slides"] = normalized_slides
    deck_plan["slide_count"] = len(normalized_slides)
    deck_plan["detected_context"] = _ensure_dict(deck_plan.get("detected_context"))
    deck_plan["theme_style"] = _ensure_dict(deck_plan.get("theme_style"))
    deck_plan["generation_rules"] = _ensure_dict(deck_plan.get("generation_rules"))
    deck_plan["data_candidates"] = _ensure_data_candidates(deck_plan.get("data_candidates"))
    deck_plan["image_candidates"] = _normalize_image_candidates(
        deck_plan.get("image_candidates"),
        normalized_slides,
    )

    deck_plan["generation_rules"].update(
        {
            "footer_text": clean_topic,
            "max_images": 3,
            "use_gradient_background": True,
            "title_on_cover": True,
            "topic_in_footer_on_each_slide": True,
            "use_editable_tables": True,
            "use_editable_charts": True,
        }
    )

    return deck_plan


def _create_json_response(client: OpenAI, user_prompt: str):
    try:
        return client.responses.create(
            model=OPENAI_TEXT_MODEL,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
    except Exception as error:
        if not _looks_like_format_error(error):
            raise

    try:
        return client.responses.create(
            model=OPENAI_TEXT_MODEL,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            text={"format": {"type": "json_object"}},
        )
    except Exception as error:
        if not _looks_like_format_error(error):
            raise

    return client.chat.completions.create(
        model=OPENAI_TEXT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )


def _looks_like_format_error(error: Exception) -> bool:
    message = str(error).lower()
    return (
        isinstance(error, TypeError)
        or "response_format" in message
        or "text.format" in message
        or "unknown parameter" in message
        or "unsupported parameter" in message
    )


def _extract_response_text(response) -> str:
    if getattr(response, "output_text", None):
        return response.output_text

    choices = getattr(response, "choices", None)
    if choices:
        message = choices[0].message
        if message and message.content:
            return message.content

    parts = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                parts.append(text)

    if parts:
        return "\n".join(parts)

    raise RuntimeError("OpenAI не вернул текст JSON")


def _build_user_prompt(
    source_text: str,
    topic: str,
    presentation_type: str,
    brand_config: dict,
    min_slides: int,
) -> str:
    schema = {
        "topic": "string",
        "presentation_type": "string",
        "slide_count": 10,
        "detected_context": {
            "main_theme": "string",
            "domain": "string",
            "audience": "string",
            "tone": "string",
            "source_summary": "string",
        },
        "theme_style": {
            "style_name": "string",
            "gradient": {"type": "linear", "from": "string", "to": "string", "accent": "string"},
            "visual_tone": "string",
            "image_style": "string",
            "chart_style": "string",
            "table_style": "string",
        },
        "generation_rules": {
            "footer_text": "string",
            "max_images": 3,
            "use_gradient_background": True,
            "title_on_cover": True,
            "topic_in_footer_on_each_slide": True,
            "use_editable_tables": True,
            "use_editable_charts": True,
        },
        "slides": [
            {
                "number": 1,
                "type": "cover",
                "title": "string",
                "subtitle": "string",
                "layout": "hero",
                "footer": "string",
                "needs_image": True,
                "needs_table": False,
                "needs_chart": False,
                "content": {"bullets": [], "speaker_note": "string"},
            }
        ],
        "data_candidates": {"tables": [], "charts": [], "dates": [], "numbers": []},
        "image_candidates": [{"slide_number": 1, "purpose": "cover", "prompt_brief": "string"}],
    }

    return (
        f"topic: {topic}\n"
        f"presentation_type: {presentation_type}\n"
        f"min_slides: {max(10, min_slides)}\n\n"
        f"brand_config:\n{json.dumps(brand_config, ensure_ascii=False, indent=2)}\n\n"
        "Требования к JSON:\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        "Жесткие правила: slides от 10 до 12; slide_count равен количеству slides; "
        "number идет по порядку; первый слайд type cover layout hero; последний type final layout final; "
        "needs_image=true максимум у 3 слайдов; image_candidates максимум 3; footer каждого слайда равен topic; "
        "видимый текст только на русском; не писать «Спасибо за внимание» как главный финальный смысл; "
        "bullets максимум 5, каждый bullet до 140 символов; title до 120 символов; "
        "subtitle до 180 символов; speaker_note до 300 символов.\n\n"
        f"extracted_text:\n{source_text}"
    )


def _trim(value: str, limit: int) -> str:
    value = " ".join((value or "").split())
    return value[:limit]


def _ensure_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _ensure_data_candidates(value) -> dict:
    value = value if isinstance(value, dict) else {}
    return {
        "tables": value.get("tables") if isinstance(value.get("tables"), list) else [],
        "charts": value.get("charts") if isinstance(value.get("charts"), list) else [],
        "dates": value.get("dates") if isinstance(value.get("dates"), list) else [],
        "numbers": value.get("numbers") if isinstance(value.get("numbers"), list) else [],
    }


def _normalize_image_candidates(value, slides: list) -> list:
    candidates = value if isinstance(value, list) else []
    result = []
    slide_numbers = {slide["number"] for slide in slides if slide.get("needs_image")}

    for candidate in candidates:
        if not isinstance(candidate, dict) or len(result) >= 3:
            continue
        slide_number = candidate.get("slide_number")
        if slide_number not in slide_numbers:
            continue
        result.append(
            {
                "slide_number": slide_number,
                "purpose": _trim(str(candidate.get("purpose") or "visual"), 80),
                "prompt_brief": _trim(str(candidate.get("prompt_brief") or ""), 300),
            }
        )

    return result
