from pathlib import Path

from dotenv import load_dotenv
import os


load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent
APP_NAME = os.getenv("APP_NAME", "AI Brand Deck Studio")
UPLOAD_DIR = BASE_DIR / os.getenv("UPLOAD_DIR", "uploads")
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "outputs")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-5.5")
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
