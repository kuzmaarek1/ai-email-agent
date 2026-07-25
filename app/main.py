from fastapi import FastAPI

from app.agent import route_message
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
    Przyjmuje zgłoszenie użytkownika, przekazuje je do Agenta AI,
    który klasyfikuje treść i wysyła e-mail do odpowiedniego działu.
    """
    department_email = await route_message(
        sender_email=payload.email,
        message=payload.message,
        subject=payload.subject,
    )

    return {
        "status": "success",
        "department_email": department_email,
    }
