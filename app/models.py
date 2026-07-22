from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class SupportRequest(BaseModel):
    """Dane wejściowe zgłoszenia od użytkownika."""

    email: EmailStr = Field(..., description="Adres e-mail nadawcy zgłoszenia")
    subject: Optional[str] = Field(None, description="Opcjonalny temat zgłoszenia")
    message: str = Field(..., min_length=1, description="Treść zgłoszenia użytkownika")
