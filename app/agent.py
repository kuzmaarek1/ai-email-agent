import json
import logging
import os
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from pydantic import BaseModel, ValidationError

from app.mailer import send_email

logger = logging.getLogger("agent")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")

# Lista dostepnych dzialow, do ktorych agent moze kierowac zgloszenia
DEPARTMENTS = {
    "human-resources": "human-resources@example.com",
    "help-desk": "help-desk@example.com",
    "it": "it@example.com",
    "kadry": "kadry@example.com",
    "other": "other@example.com",
}

SYSTEM_PROMPT = """Jestes agentem klasyfikujacym zgloszenia uzytkownikow do odpowiedniego dzialu firmy.

Wybierz jeden adres department_email na podstawie tresci zgloszenia:
- it@example.com: problemy techniczne, komputer, sprzet, oprogramowanie, dostepy, awarie
- kadry@example.com: urlopy, zwolnienia lekarskie, wynagrodzenia, sprawy pracownicze
- human-resources@example.com: rekrutacja, umowy, sprawy kadrowo-personalne
- help-desk@example.com: ogolne pytania i wsparcie, niejednoznaczne zgloszenia
- other@example.com: wszystko inne, co nie pasuje do powyzszych

Odpowiedz WYLACZNIE poprawnym JSON-em w formacie:
{"department_email": "<jeden adres z listy powyzej>"}

Nie dodawaj zadnego tekstu poza tym JSON-em."""


class AgentDecision(BaseModel):
    """
    Oczekiwany ksztalt odpowiedzi modelu. Pole department_email jest ograniczone
    typem Literal do dokladnie tych 5 adresow - jesli model zwroci cokolwiek
    innego (zly adres, literowka, spoza listy), Pydantic zgłosi ValidationError
    i kod przechodzi do fallbacku "other@example.com" zamiast wyslac blad dalej.
    """

    department_email: Literal[
        "human-resources@example.com",
        "help-desk@example.com",
        "it@example.com",
        "kadry@example.com",
        "other@example.com",
    ]

# format="json" wymusza na Ollamie generowanie poprawnego strukturalnie JSON-a
# (gramatyczne ograniczenie dekodowania) - duzo bardziej niezawodne niz
# poleganie na natywnym tool_calls przy malych modelach lokalnych.
llm = ChatOllama(
    base_url=OLLAMA_HOST,
    model=OLLAMA_MODEL,
    temperature=0,
    num_predict=64,  # model zwraca tylko jedno krotkie pole, wiec mniejszy limit wystarczy
    format="json",
)


def _build_send_tool(sender_email: str):
    """
    Buduje narzedzie wysylki maila 'zamkniete' na konkretnym nadawcy zgloszenia,
    zeby model nie musial (i nie mogl) samodzielnie zmyslac adresu Reply-To.
    """

    @tool
    async def send_department_email(department_email: str, subject: str, body: str) -> str:
        """
        Wysyla wiadomosc e-mail do wskazanego dzialu firmy.

        Args:
            department_email: adres e-mail dzialu docelowego, musi byc jednym z dozwolonych adresow
            subject: temat wiadomosci
            body: tresc wiadomosci
        """
        valid_addresses = set(DEPARTMENTS.values())
        target = department_email if department_email in valid_addresses else DEPARTMENTS["other"]

        await send_email(
            to_address=target,
            reply_to=sender_email,
            subject=subject,
            body=body,
        )

        return f"Wiadomosc przekazana do {target}"

    return send_department_email


async def route_message(sender_email: str, message: str, subject: str | None = None) -> str:
    """
    Uruchamia Agenta AI. Model analizuje wiadomosc i decyduje TYLKO o dziale
    docelowym (department_email) - to jedyne pole generowane przez model, co
    zwieksza niezawodnosc. Temat i tresc pochodza bezposrednio z requestu
    uzytkownika, bez przepisywania ich przez model. Na podstawie tej decyzji
    kod wywoluje narzedzie send_department_email (function calling), aby
    faktycznie wyslac maila. Zwraca adres e-mail dzialu docelowego.
    """
    send_tool = _build_send_tool(sender_email)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=message),
    ]

    response = await llm.ainvoke(messages)
    logger.warning("DEBUG raw response: %r", response.content)

    department_email = DEPARTMENTS["other"]

    try:
        decision = AgentDecision.model_validate_json(response.content)
        department_email = decision.department_email
    except (ValidationError, json.JSONDecodeError, TypeError) as exc:
        # Model zwrocil niepoprawny JSON albo adres spoza dozwolonej listy.
        # Nie przerywamy dzialania - zgloszenie i tak trafia dalej, tylko
        # do dzialu "other" (bezpieczny fallback), a blad jest logowany
        # do dalszej analizy/debugowania.
        logger.warning("Niepoprawna odpowiedz modelu, uzywam fallbacku 'other': %s", exc)

    final_subject = subject or "Nowe zgloszenie"
    final_body = message

    result = await send_tool.ainvoke(
        {"department_email": department_email, "subject": final_subject, "body": final_body}
    )
    logger.warning("DEBUG tool result: %r", result)

    return department_email