import json
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.ai_service import analyze_document_context_with_ai, build_slide_plan_with_ai
from app.brand_service import get_default_brand_config
from app.config import APP_NAME, OPENAI_TEXT_MODEL
from app.deck_service import (
    attach_visual_assets_to_slide_plan,
    build_empty_document_diagnostics,
    build_fallback_slide_plan,
    build_mvp_deck_plan_from_slide_plan,
    final_deck_quality_gate,
    load_deck_plan,
    prepare_mvp_deck_plan,
    run_data_quality_gate,
    run_text_quality_gate,
    run_visual_quality_gate,
    save_deck_plan,
    validate_slide_roles_and_layouts,
)
from app.file_service import extract_text_from_file, save_uploaded_file


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
    project_id = uuid4().hex

    plan_source = OPENAI_TEXT_MODEL
    document_diagnostics_error = ""
    slide_plan_error = ""
    ai_error = ""
    analysis_error = ""
    visual_assets_note = (
        "Генерация изображений отключена: используются только локальные фоны "
        "и иконки из static/assets."
    )

    try:
        document_diagnostics = analyze_document_context_with_ai(
            extracted_text=extracted_text,
            topic=topic,
            presentation_type=deck_type,
        )
    except Exception as error:
        document_diagnostics_error = str(error)
        document_diagnostics = build_empty_document_diagnostics()

    document_context = document_diagnostics.get("document_context", {})
    verified_facts = document_diagnostics.get("verified_facts", {})

    try:
        slide_plan = build_slide_plan_with_ai(
            extracted_text=extracted_text,
            topic=topic,
            presentation_type=deck_type,
            document_context=document_context,
            verified_facts=verified_facts,
            min_slides=5,
        )
    except Exception as error:
        slide_plan_error = str(error)
        plan_source = "локальный fallback"
        slide_plan = build_fallback_slide_plan(
            document_context=document_context,
            topic=topic,
            presentation_type=deck_type,
            min_slides=5,
        )

    slide_plan = validate_slide_roles_and_layouts(slide_plan)
    slide_plan = run_text_quality_gate(slide_plan)
    slide_plan = run_data_quality_gate(slide_plan, verified_facts)
    slide_plan = run_visual_quality_gate(slide_plan, document_context)
    slide_plan = attach_visual_assets_to_slide_plan(slide_plan, document_context)

    deck_plan = build_mvp_deck_plan_from_slide_plan(
        topic=topic,
        presentation_type=deck_type,
        slide_plan=slide_plan,
        document_context=document_context,
        verified_facts=verified_facts,
    )
    deck_plan["hero_visual_warnings"] = [visual_assets_note]
    quality_report = final_deck_quality_gate(deck_plan)
    deck_plan["quality_report"] = quality_report
    save_deck_plan(deck_plan, project_id=project_id)

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
            "source_analysis": {},
            "document_context": document_context,
            "verified_facts": verified_facts,
            "slide_plan": deck_plan.get("slide_plan", []),
            "slide_plan_quality_warnings": deck_plan.get("slide_plan_quality_warnings", []),
            "hero_visual_warnings": deck_plan.get("hero_visual_warnings", []),
            "deck_plan": deck_plan,
            "deck_plan_json": json.dumps(deck_plan, ensure_ascii=False, indent=2),
            "project_id": project_id,
            "plan_source": plan_source,
            "document_diagnostics_error": document_diagnostics_error,
            "slide_plan_error": slide_plan_error,
            "analysis_error": analysis_error,
            "ai_error": ai_error,
            "quality_report": quality_report,
            "png_assets_warning": visual_assets_note,
        },
    )


@router.get("/deck/{project_id}", response_class=HTMLResponse)
async def deck(request: Request, project_id: str):
    try:
        deck_plan = load_deck_plan(project_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    deck_plan = prepare_mvp_deck_plan(deck_plan)

    return templates.TemplateResponse(
        request,
        "deck.html",
        {
            "app_name": APP_NAME,
            "project_id": project_id,
            "deck_plan": deck_plan,
            "brand_config": get_default_brand_config(),
            "debug": request.query_params.get("debug") == "1",
        },
    )


@router.get("/health")
async def health():
    return {"status": "ok"}
