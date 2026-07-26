import asyncio
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

# Zabezpieczenie na wypadek gdyby model "zapetlil sie" i nie skonczyl
# generowania (obserwowane w testach na malych, lokalnych modelach). Bez
# timeoutu request wisialby w nieskonczonosc.
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "120"))

# Lista dostepnych dzialow, do ktorych agent moze kierowac zgloszenia
DEPARTMENTS = {
    "human-resources": "human-resources@example.com",
    "help-desk": "help-desk@example.com",
    "it": "it@example.com",
    "kadry": "kadry@example.com",
    "other": "other@example.com",
}

SYSTEM_PROMPT = """Jestes agentem klasyfikujacym zgloszenia uzytkownikow do odpowiedniego dzialu firmy.

Przeanalizuj tresc zgloszenia i wywolaj narzedzie send_department_email, przekazujac
jako department_email jeden z ponizszych adresow:
- it@example.com: problemy techniczne, komputer, sprzet, oprogramowanie, dostepy, awarie
- kadry@example.com: urlopy, zwolnienia lekarskie, wynagrodzenia, sprawy pracownicze
- human-resources@example.com: rekrutacja, umowy, sprawy kadrowo-personalne
- help-desk@example.com: ogolne pytania i wsparcie, niejednoznaczne zgloszenia
- other@example.com: wszystko inne, co nie pasuje do powyzszych

Zawsze musisz wywolac narzedzie send_department_email - nie odpowiadaj samym tekstem."""

# Uzywany WYLACZNIE w sciezce fallback, gdy model nie zwrocil tool_calls.
# Wymusza czysta klasyfikacje w formacie JSON (bez proby wywolania narzedzia),
# zeby fallback faktycznie klasyfikowal zgloszenie, a nie zgadywal na slepo
# na podstawie tekstu z pierwszej proby (ktora nie byla w formacie JSON).
FALLBACK_CLASSIFICATION_PROMPT = """Jestes agentem klasyfikujacym zgloszenia uzytkownikow do odpowiedniego dzialu firmy.

Wybierz jeden adres department_email na podstawie tresci zgloszenia:
- it@example.com: problemy techniczne, komputer, sprzet, oprogramowanie, dostepy, awarie
- kadry@example.com: urlopy, zwolnienia lekarskie, wynagrodzenia, sprawy pracownicze
- human-resources@example.com: rekrutacja, umowy, sprawy kadrowo-personalne
- help-desk@example.com: ogolne pytania i wsparcie, niejednoznaczne zgloszenia
- other@example.com: wszystko inne, co nie pasuje do powyzszych

Odpowiedz WYLACZNIE poprawnym JSON-em w formacie:
{"department_email": "<jeden adres z listy powyzej>"}

Nie dodawaj zadnego tekstu poza tym JSON-em."""

# Wartosci pola routing_method zwracanego z route_message - pokazuje, ktora
# sciezka faktycznie obsluzyla zgloszenie: natywny tool calling modelu,
# czy zapasowa klasyfikacja przez osobne wywolanie z format="json".
RoutingMethod = Literal["tool_calls", "fallback"]


class AgentDecision(BaseModel):
    """
    Uzywane wylacznie jako fallback, gdyby model NIE zwrocil tool_calls
    (co zdarza sie na malych, lokalnych modelach). Pole department_email
    jest ograniczone typem Literal do dokladnie tych 5 adresow.
    """

    department_email: Literal[
        "human-resources@example.com",
        "help-desk@example.com",
        "it@example.com",
        "kadry@example.com",
        "other@example.com",
    ]


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


async def route_message(
    sender_email: str, message: str, subject: str | None = None
) -> tuple[str, RoutingMethod]:
    """
    Uruchamia Agenta AI. Model dostaje narzedzie send_department_email przez
    bind_tools() i SAM decyduje, czy i z jakimi argumentami je wywolac
    (prawdziwy tool/function calling, response.tool_calls) - to jest glowna
    sciezka dzialania.

    Fallback: jesli model (np. z powodu ograniczen malego, lokalnego LLM-a)
    nie zwroci zadnego tool_calls, wykonujemy DRUGIE wywolanie modelu z
    format="json" wylacznie w celu klasyfikacji, a nastepnie kod recznie
    wywoluje narzedzie na podstawie tej klasyfikacji - zgloszenie i tak
    zostaje obsluzone (bezpieczny fallback do "other", a nie blad 500).

    Timeout: kazde wywolanie LLM jest ograniczone czasowo (LLM_TIMEOUT_SECONDS),
    zeby zabezpieczyc sie przed przypadkiem, gdy maly, lokalny model "zapetli
    sie" i nie zakonczy generowania odpowiedzi. Przekroczenie timeoutu w
    glownej probie traktowane jest jak brak tool_calls (przejscie do
    fallbacku); przekroczenie timeoutu rowniez w fallbacku konczy sie
    bezpiecznym przypisaniem do "other".

    Zwraca krotke (department_email, routing_method) - routing_method
    pozwala jednoznacznie sprawdzic z zewnatrz (np. w odpowiedzi API), czy
    zgloszenie zostalo obsluzone przez natywny tool calling modelu, czy przez
    sciezke zapasowa. Przydatne przy demonstrowaniu/testowaniu PoC, zeby nie
    trzeba bylo zagladac do logow serwera.
    """
    send_tool = _build_send_tool(sender_email)
    llm = ChatOllama(
        base_url=OLLAMA_HOST,
        model=OLLAMA_MODEL,
        temperature=0,
        num_predict=256,  # ogranicza dlugosc odpowiedzi, dodatkowa ochrona przed zapetleniem
    )
    llm_with_tools = llm.bind_tools([send_tool])

    final_subject = subject or "Nowe zgloszenie"

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Temat: {final_subject}\nTresc zgloszenia: {message}"),
    ]

    tool_calls = []
    try:
        response = await asyncio.wait_for(
            llm_with_tools.ainvoke(messages), timeout=LLM_TIMEOUT_SECONDS
        )
        tool_calls = response.tool_calls
        logger.warning("DEBUG response.tool_calls: %r", tool_calls)
        logger.warning("DEBUG response.content: %r", response.content)
    except asyncio.TimeoutError:
        # Model nie zdazyl odpowiedziec w rozsadnym czasie (np. zapetlenie
        # generowania) - traktujemy to jak brak tool_calls i przechodzimy
        # do sciezki zapasowej zamiast wieszac request.
        logger.warning(
            "Timeout (%ss) przy wywolaniu glownego LLM, przechodze do fallbacku",
            LLM_TIMEOUT_SECONDS,
        )

    if tool_calls:
        # Glowna sciezka: model sam zdecydowal wywolac narzedzie.
        call = tool_calls[0]
        args = call.get("args", {})

        department_email = args.get("department_email", DEPARTMENTS["other"])
        if department_email not in set(DEPARTMENTS.values()):
            department_email = DEPARTMENTS["other"]

        result = await send_tool.ainvoke(
            {
                "department_email": department_email,
                "subject": args.get("subject") or final_subject,
                "body": args.get("body") or message,
            }
        )
        logger.warning("DEBUG tool result (native tool_calls): %r", result)
        return department_email, "tool_calls"

    # Fallback - model nie wywolal narzedzia (zdarza sie na malych, lokalnych
    # modelach). Robimy DRUGIE, osobne wywolanie modelu z format="json", zeby
    # wymusic gramatycznie poprawna klasyfikacje, zamiast probowac wyciagnac
    # cokolwiek z tekstu pierwszej proby (ktora nie byla w formacie JSON i
    # prawie na pewno nie da sie jej sparsowac).
    logger.warning("Model nie zwrocil tool_calls, uzywam sciezki fallback (druga proba)")

    classifier_llm = ChatOllama(
        base_url=OLLAMA_HOST,
        model=OLLAMA_MODEL,
        temperature=0,
        num_predict=64,
        format="json",
    )

    department_email = DEPARTMENTS["other"]
    try:
        classification_response = await asyncio.wait_for(
            classifier_llm.ainvoke(
                [
                    SystemMessage(content=FALLBACK_CLASSIFICATION_PROMPT),
                    HumanMessage(content=message),
                ]
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )
        logger.warning("DEBUG fallback raw response: %r", classification_response.content)
        decision = AgentDecision.model_validate_json(classification_response.content)
        department_email = decision.department_email
    except asyncio.TimeoutError:
        # Nawet sciezka zapasowa nie zdazyla odpowiedziec - laduje do "other",
        # zeby request i tak sie zakonczyl, a nie zawisl bez konca.
        logger.warning(
            "Timeout (%ss) rowniez przy fallbacku, uzywam 'other'", LLM_TIMEOUT_SECONDS
        )
    except (ValidationError, json.JSONDecodeError, TypeError) as exc:
        logger.warning("Fallback: niepoprawna odpowiedz modelu, uzywam 'other': %s", exc)

    result = await send_tool.ainvoke(
        {"department_email": department_email, "subject": final_subject, "body": message}
    )
    logger.warning("DEBUG tool result (fallback path): %r", result)

    return department_email, "fallback"