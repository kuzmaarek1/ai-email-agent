import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")

DEPARTMENTS = {
    "human-resources": "human-resources@example.com",
    "help-desk": "help-desk@example.com",
    "it": "it@example.com",
    "kadry": "kadry@example.com",
    "other": "other@example.com",
}

SYSTEM_PROMPT = """
Jestes agentem klasyfikujacym zgloszenia uzytkownikow do odpowiedniego dzialu firmy.

Dostepne dzialy:
- human-resources@example.com - sprawy kadrowo-personalne (rekrutacja, umowy, ogolne sprawy HR)
- kadry@example.com - sprawy pracownicze (urlopy, zwolnienia lekarskie, wynagrodzenia)
- it@example.com - problemy techniczne, sprzet, oprogramowanie, dostepy
- help-desk@example.com - ogolne wsparcie, pytania niejednoznaczne technicznie
- other@example.com - wszystko, co nie pasuje jednoznacznie do powyzszych

Zwroc WYLACZNIE jeden adres e-mail z powyzszej listy, bez zadnego dodatkowego tekstu.
"""

llm = ChatOllama(
    base_url=OLLAMA_HOST,
    model=OLLAMA_MODEL,
    temperature=0,
)


async def classify_message(message: str) -> str:
    """
    Na tym etapie agent TYLKO klasyfikuje wiadomosc i zwraca adres dzialu.
    Wysylka maila (function calling) zostanie dodana w kolejnym kroku.
    """
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=message),
    ]
    response = await llm.ainvoke(messages)
    answer = response.content.strip()

    for address in DEPARTMENTS.values():
        if address in answer:
            return address

    return DEPARTMENTS["other"]
