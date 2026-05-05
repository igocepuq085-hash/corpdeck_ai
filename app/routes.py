import json
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.ai_service import analyze_source_material_with_ai, generate_deck_plan_with_ai, validate_and_normalize_deck_plan
from app.brand_service import get_default_brand_config
from app.config import APP_NAME, OPENAI_TEXT_MODEL
from app.decor_service import attach_decor_layers_to_deck_plan
from app.deck_service import (
    attach_generated_png_assets_to_deck_plan,
    build_draft_deck_plan,
    build_local_source_analysis,
    evaluate_deck_quality,
    load_deck_plan,
    save_deck_plan,
)
from app.file_service import extract_text_from_file, save_uploaded_file
from app.image_service import generate_slide_png_assets


router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "app_name": "AI Brand Deck Studio",
            "description": "Сервис генерации и улучшения корпоративных презентаций",
        },
    )


@router.post("/upload", response_class=HTMLResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    topic: str = Form(...),
    deck_type: str = Form(...),
):
    saved_path = save_uploaded_file(file)
    extraction = extract_text_from_file(str(saved_path))
    extracted_text = extraction.get("text", "")
    brand_config = get_default_brand_config()
    plan_source = OPENAI_TEXT_MODEL
    analysis_error = ""
    ai_error = ""
    png_assets_warning = ""

    try:
        source_analysis = analyze_source_material_with_ai(
            extracted_text=extracted_text,
            topic=topic,
            presentation_type=deck_type,
            brand_config=brand_config,
        )
    except Exception as error:
        analysis_error = str(error)
        source_analysis = build_local_source_analysis(
            extracted_text=extracted_text,
            topic=topic,
            presentation_type=deck_type,
        )

    try:
        deck_plan = generate_deck_plan_with_ai(
            extracted_text=extracted_text,
            topic=topic,
            presentation_type=deck_type,
            brand_config=brand_config,
            source_analysis=source_analysis,
        )
        if not deck_plan:
            raise RuntimeError("OpenAI не вернул план презентации")
        deck_plan = validate_and_normalize_deck_plan(deck_plan, topic, source_analysis=source_analysis)
    except Exception as error:
        ai_error = str(error)
        plan_source = "локальная эвристика"
        deck_plan = build_draft_deck_plan(
            extracted_text=extracted_text,
            topic=topic,
            presentation_type=deck_type,
        )

    quality_report = evaluate_deck_quality(deck_plan, source_analysis)
    deck_plan["quality_report"] = quality_report
    project_id = uuid4().hex

    try:
        generated_png_assets = generate_slide_png_assets(
            project_id=project_id,
            deck_plan=deck_plan,
            brand_config=brand_config,
            max_assets=8,
        )
    except Exception as error:
        generated_png_assets = []
        png_assets_warning = str(error)

    deck_plan = attach_generated_png_assets_to_deck_plan(deck_plan, generated_png_assets)
    deck_plan = attach_decor_layers_to_deck_plan(deck_plan)
    quality_report = evaluate_deck_quality(deck_plan, source_analysis)
    deck_plan["quality_report"] = quality_report
    save_deck_plan(deck_plan, project_id=project_id)
    generated_ok = [item for item in generated_png_assets if item.get("status") == "ok"]

    return templates.TemplateResponse(
        request,
        "preview.html",
        {
            "app_name": APP_NAME,
            "filename": file.filename,
            "saved_filename": saved_path.name,
            "topic": topic,
            "deck_type": deck_type,
            "extraction": extraction,
            "source_analysis": source_analysis,
            "deck_plan": deck_plan,
            "deck_plan_json": json.dumps(deck_plan, ensure_ascii=False, indent=2),
            "project_id": project_id,
            "plan_source": plan_source,
            "analysis_error": analysis_error,
            "ai_error": ai_error,
            "quality_report": quality_report,
            "generated_png_assets": generated_png_assets,
            "generated_png_assets_count": len(generated_ok),
            "png_assets_warning": png_assets_warning,
        },
    )


@router.get("/deck/{project_id}", response_class=HTMLResponse)
async def deck(request: Request, project_id: str):
    try:
        deck_plan = load_deck_plan(project_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return templates.TemplateResponse(
        request,
        "deck.html",
        {
            "app_name": APP_NAME,
            "project_id": project_id,
            "deck_plan": deck_plan,
            "brand_config": get_default_brand_config(),
        },
    )


@router.get("/health")
async def health():
    return {"status": "ok"}
