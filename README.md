# AI Support API

API wykorzystujace Agenta AI do analizy zgloszen i automatycznego kierowania wiadomosci e-mail do odpowiedniego dzialu. Wiadomosci sa wysylane przy uzyciu function calling i przechwytywane przez MailHog.

## Technologie

- Python 3.12
- FastAPI
- Pydantic AI
- Ollama (obraz `alpine/ollama` - lekka wersja CPU-only)
- MailHog
- Docker Compose

## Architektura

Projekt sklada sie z trzech serwisow:

- **api** - aplikacja FastAPI udostepniajaca endpoint REST oraz dokumentacje Swagger.
- **ollama** - lokalny model LLM wykorzystywany przez Agenta. Wykorzystujemy obraz `alpine/ollama` zamiast oficjalnego `ollama/ollama`, poniewaz jest znacznie lzejszy (rozwiazanie dziala wylacznie na CPU, co jest zgodne z wymaganiami zadania).
- **mailhog** - lokalny serwer SMTP sluzacy do testowania wysylki wiadomosci e-mail.

Agent analizuje tresc zgloszenia, wybiera odpowiedni dzial i wywoluje funkcje odpowiedzialna za wyslanie wiadomosci e-mail.

## Uruchomienie

```bash
docker compose up -d
```

Po uruchomieniu kontenerow nalezy jednorazowo pobrac model LLM do kontenera Ollama (obraz nie zawiera domyslnie zadnych wag):

```bash
docker exec -it ollama ollama pull qwen2.5:0.5b
```

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

2. Pobierz model do Ollamy (jednorazowo):

   ```bash
   docker exec -it ollama ollama pull qwen2.5:0.5b
   ```

3. Wyslij przykladowe zadanie.

4. Otworz MailHog:

   ```
   http://localhost:8025
   ```

5. Sprawdz, czy:
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
│   ├── agent.py       # Agent AI (pydantic-ai + Ollama) z tool callingiem
│   └── mailer.py      # wysylka e-maili przez SMTP (MailHog)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```
