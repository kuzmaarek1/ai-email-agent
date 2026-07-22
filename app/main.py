from fastapi import FastAPI

from app.agent import classify_message
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
    Endpoint klasyfikuje zgłoszenie przy pomocy Agenta AI i zwraca dział docelowy.
    Wysyłka e-maila zostanie podłączona w kolejnym etapie.
    """
    department_email = await classify_message(payload.message)

    return {
        "received_email": payload.email,
        "department_email": department_email,
    }
