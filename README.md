# AI Support API

API wykorzystujące Agenta AI do analizy zgłoszeń i automatycznego kierowania wiadomości e-mail do odpowiedniego działu. Wiadomości są wysyłane przy użyciu function calling i przechwytywane przez MailHog.

## Technologie

- Python 3.12
- FastAPI
- Pydantic AI
- Ollama
- MailHog
- Docker Compose

## Architektura

Projekt składa się z trzech serwisów:

- **api** – aplikacja FastAPI udostępniająca endpoint REST oraz dokumentację Swagger.
- **ollama** – lokalny model LLM wykorzystywany przez Agenta.
- **mailhog** – lokalny serwer SMTP służący do testowania wysyłki wiadomości e-mail.

Agent analizuje treść zgłoszenia, wybiera odpowiedni dział i wywołuje funkcję odpowiedzialną za wysłanie wiadomości e-mail.

## Uruchomienie

```bash
docker compose up -d
```

Po uruchomieniu dostępne są:

| Adres                             | Opis          |
| --------------------------------- | ------------- |
| http://localhost:8000/api/v1/docs | Swagger UI    |
| http://localhost:8025             | Panel MailHog |
| http://localhost:11434            | Ollama        |

## Przykładowe wywołanie API

```bash
curl -X POST http://localhost:8000/api/v1/support \
-H "Content-Type: application/json" \
-d '{
  "sender":"jan@example.com",
  "subject":"Problem z fakturą",
  "message":"Nie otrzymałem faktury za zamówienie."
}'
```

## Przykładowa odpowiedź

```json
{
  "status": "success",
  "department": "billing"
}
```

## Testowanie

1. Uruchom projekt:

   ```bash
   docker compose up -d
   ```

2. Wyślij przykładowe żądanie.

3. Otwórz MailHog:

   ```
   http://localhost:8025
   ```

4. Sprawdź, czy:
   - wiadomość została wysłana,
   - odbiorca jest poprawnym działem,
   - nagłówek `Reply-To` zawiera adres nadawcy.

## Struktura projektu

```
.
├── app/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
└── openapi.yaml
```
