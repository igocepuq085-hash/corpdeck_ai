import json

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.ai_service import generate_deck_plan_with_ai
from app.brand_service import get_default_brand_config
from app.config import APP_NAME, OPENAI_TEXT_MODEL
from app.deck_service import (
    attach_generated_images_to_deck_plan,
    build_draft_deck_plan,
    load_deck_plan,
    save_deck_plan,
)
from app.file_service import extract_text_from_file, save_uploaded_file
from app.image_service import generate_slide_images


router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
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
    ai_error = ""

    try:
        deck_plan = generate_deck_plan_with_ai(
            extracted_text=extracted_text,
            topic=topic,
            presentation_type=deck_type,
            brand_config=brand_config,
        )
        if not deck_plan:
            raise RuntimeError("OpenAI не вернул план презентации")
    except Exception as error:
        ai_error = str(error)
        plan_source = "локальная эвристика"
        deck_plan = build_draft_deck_plan(
            extracted_text=extracted_text,
            topic=topic,
            presentation_type=deck_type,
        )

    project_id = save_deck_plan(deck_plan)
    generated_images = generate_slide_images(
        project_id=project_id,
        deck_plan=deck_plan,
        brand_config=brand_config,
        max_images=5,
    )
    deck_plan = attach_generated_images_to_deck_plan(deck_plan, generated_images)
    save_deck_plan(deck_plan, project_id=project_id)
    generated_ok = [item for item in generated_images if item.get("status") == "ok"]

    return templates.TemplateResponse(
        "preview.html",
        {
            "request": request,
            "app_name": APP_NAME,
            "filename": file.filename,
            "saved_filename": saved_path.name,
            "topic": topic,
            "deck_type": deck_type,
            "extraction": extraction,
            "deck_plan": deck_plan,
            "deck_plan_json": json.dumps(deck_plan, ensure_ascii=False, indent=2),
            "project_id": project_id,
            "plan_source": plan_source,
            "ai_error": ai_error,
            "generated_images": generated_images,
            "generated_images_count": len(generated_ok),
        },
    )


@router.get("/deck/{project_id}", response_class=HTMLResponse)
async def deck(request: Request, project_id: str):
    try:
        deck_plan = load_deck_plan(project_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return templates.TemplateResponse(
        "deck.html",
        {
            "request": request,
            "app_name": APP_NAME,
            "project_id": project_id,
            "deck_plan": deck_plan,
            "brand_config": get_default_brand_config(),
        },
    )


@router.get("/health")
async def health():
    return {"status": "ok"}
