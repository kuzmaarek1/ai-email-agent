from fastapi import FastAPI

from app.models import SupportRequest

app = FastAPI(
    title="AI Support API",
    docs_url="/api/v1/docs",
)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/api/v1/support")
async def submit_support_request(payload: SupportRequest):
    """
    Na tym etapie endpoint tylko przyjmuje i waliduje zgłoszenie.
    Klasyfikacja i wysyłka maila zostaną dodane w kolejnych krokach.
    """
    return {
        "received_email": payload.email,
        "received_message": payload.message,
    }
