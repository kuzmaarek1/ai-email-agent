# AI Support API

API wykorzystujace Agenta AI do analizy zgloszen i automatycznego kierowania wiadomosci e-mail do odpowiedniego dzialu. Wiadomosci sa wysylane przy uzyciu function calling i przechwytywane przez MailHog.

## Technologie

- Python 3.12
- FastAPI
- LangChain (langchain-ollama)
- Ollama (obraz `ollama/ollama`)
- MailHog
- Docker Compose

## Architektura

Projekt sklada sie z czterech serwisow:

- **api** - aplikacja FastAPI udostepniajaca endpoint REST oraz dokumentacje Swagger.
- **ollama** - lokalny model LLM wykorzystywany przez Agenta. Wykorzystujemy oficjalny obraz `ollama/ollama`, dziala w trybie CPU-only (bez sekcji GPU w konfiguracji), co jest zgodne z wymaganiami zadania.
- **ollama-init** - jednorazowy serwis inicjujacy, ktory automatycznie pobiera wagi modelu przy pierwszym uruchomieniu srodowiska (`ollama pull`). Konczy dzialanie po pobraniu modelu; `api` czeka na jego pomyslne zakonczenie (`service_completed_successfully`) zanim wystartuje.
- **mailhog** - lokalny serwer SMTP sluzacy do testowania wysylki wiadomosci e-mail.

Agent analizuje tresc zgloszenia, wybiera odpowiedni dzial i wywoluje funkcje odpowiedzialna za wyslanie wiadomosci e-mail.

## Uruchomienie

```bash
docker compose up -d
```

Srodowisko uruchamia sie w pelni automatycznie: kontener `ollama` startuje, healthcheck potwierdza jego gotowosc, serwis `ollama-init` pobiera wagi modelu (`qwen2.5:0.5b`, ~400MB), a dopiero po jego pomyslnym zakonczeniu startuje `api`. Nie sa wymagane zadne dodatkowe komendy - po `docker compose up -d` srodowisko jest w pelni gotowe do przyjmowania requestow.

Wybrano lekki model `qwen2.5:0.5b` (~400MB), poniewaz zadanie klasyfikacji krotkich wiadomosci do jednego z 5 dzialow nie wymaga duzego modelu, a znacznie przyspiesza to dzialanie na CPU.

Dostepne sa wtedy:

| Adres                             | Opis          |
| --------------------------------- | ------------- |
| http://localhost:8000/api/v1/docs | Swagger UI    |
| http://localhost:8025             | Panel MailHog |
| http://localhost:11434            | Ollama        |

## Przykladowe wywolanie API

```bash
curl -X POST http://localhost:8000/api/v1/support \
-H "Content-Type: application/json" \
-d '{
  "email":"jan@example.com",
  "subject":"Awaria komputera",
  "message":"Nie dziala mi komputer, ekran jest czarny i nie moge sie zalogowac."
}'
```

> **Uwaga (Windows / PowerShell):** domyslny `curl` w PowerShell to alias dla `Invoke-WebRequest` i inaczej obsluguje cudzyslowy. Jesli powyzsza komenda nie zadziala, uzyj Swaggera pod `/api/v1/docs` albo zapisz JSON do pliku i wyslij go przez `-d "@body.json"`.

## Przykladowa odpowiedz

```json
{
  "status": "success",
  "department_email": "it@example.com"
}
```

## Testowanie

1. Uruchom projekt:

   ```bash
   docker compose up -d
   ```

2. Wyslij przykladowe zadanie.

3. Otworz MailHog:

   ```
   http://localhost:8025
   ```

4. Sprawdz, czy:
   - wiadomosc zostala wyslana,
   - odbiorca jest poprawnym dzialem,
   - naglowek `Reply-To` zawiera adres nadawcy.

## Struktura projektu

```
.
├── app/
│   ├── __init__.py
│   ├── main.py       # endpoint FastAPI + konfiguracja Swagger
│   ├── models.py     # modele Pydantic (request/response)
│   ├── agent.py       # Agent AI (LangChain + Ollama) z tool callingiem
│   └── mailer.py      # wysylka e-maili przez SMTP (MailHog)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```
