from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class SupportRequest(BaseModel):
    """Dane wejściowe zgłoszenia od użytkownika."""

    email: EmailStr = Field(..., description="Adres e-mail nadawcy zgłoszenia")
    subject: Optional[str] = Field(None, description="Opcjonalny temat zgłoszenia")
    message: str = Field(..., min_length=1, description="Treść zgłoszenia użytkownika")


class SupportResponse(BaseModel):
    """Odpowiedź API po przetworzeniu zgłoszenia przez Agenta."""

    status: str = Field(..., description="Status przetworzenia zgłoszenia")
    department_email: str = Field(..., description="Adres e-mail działu, do którego skierowano zgłoszenie")
    routing_method: Literal["tool_calls", "fallback"] = Field(
        ...,
        description=(
            "Sposob w jaki Agent podjal decyzje: 'tool_calls' oznacza, ze model "
            "sam wywolal narzedzie send_department_email (natywny tool/function "
            "calling); 'fallback' oznacza, ze model nie zwrocil tool_calls i "
            "zadzialala zapasowa sciezka klasyfikacji (osobne wywolanie modelu "
            "z wymuszonym formatem JSON)."
        ),
    )