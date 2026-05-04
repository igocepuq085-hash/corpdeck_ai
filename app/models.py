from pydantic import BaseModel


class UploadedDeckInfo(BaseModel):
    filename: str
    topic: str
    deck_type: str

