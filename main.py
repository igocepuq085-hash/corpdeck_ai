import os

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import router


app = FastAPI(title="AI Brand Deck Studio")

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
