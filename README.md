# AI Support API

API wykorzystujące Agenta AI do analizy zgłoszeń i automatycznego kierowania wiadomości e-mail do odpowiedniego działu. Wiadomości są wysyłane przy użyciu function calling i przechwytywane przez MailHog.

## Technologie

- Python 3.12
- FastAPI
- Pydantic AI
- Ollama (obraz `alpine/ollama` — lekka wersja CPU-only)
- MailHog
- Docker Compose

## Architektura

Projekt składa się z trzech serwisów:

- **api** – aplikacja FastAPI udostępniająca endpoint REST oraz dokumentację Swagger.
- **ollama** – lokalny model LLM wykorzystywany przez Agenta. Wykorzystujemy obraz `alpine/ollama` zamiast oficjalnego `ollama/ollama`, ponieważ jest znacznie lżejszy (rozwiązanie działa wyłącznie na CPU, co jest zgodne z wymaganiami zadania).
- **mailhog** – lokalny serwer SMTP służący do testowania wysyłki wiadomości e-mail.

Agent analizuje treść zgłoszenia, wybiera odpowiedni dział i wywołuje funkcję odpowiedzialną za wysłanie wiadomości e-mail.

## Uruchomienie

```bash
docker compose up -d
```

Po uruchomieniu kontenerów należy jednorazowo pobrać model LLM do kontenera Ollama (obraz nie zawiera domyślnie żadnych wag):

```bash
docker exec -it ollama ollama pull qwen2.5:0.5b
```

Wybrano lekki model `qwen2.5:0.5b` (~400MB), ponieważ zadanie klasyfikacji krótkich wiadomości do jednego z 5 działów nie wymaga dużego modelu, a znacznie przyspiesza to działanie na CPU.

Dostępne są wtedy:

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

2. Pobierz model do Ollamy (jednorazowo):

   ```bash
   docker exec -it ollama ollama pull qwen2.5:0.5b
   ```

3. Wyślij przykładowe żądanie.

4. Otwórz MailHog:

   ```
   http://localhost:8025
   ```

5. Sprawdź, czy:
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
