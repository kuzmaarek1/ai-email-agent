# AI Support API

API wykorzystujace Agenta AI do analizy zgloszen i automatycznego kierowania wiadomosci e-mail do odpowiedniego dzialu. Wiadomosci sa wysylane przy uzyciu function calling i przechwytywane przez MailHog.

## Technologie

- Python 3.12
- FastAPI
- Pydantic (walidacja requestow/odpowiedzi API oraz walidacja decyzji zwracanej przez model AI)
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

Agent analizuje tresc zgloszenia i decyduje, do jakiego dzialu ja skierowac (model zwraca ustrukturyzowana decyzje w formacie JSON, wymuszonym przez Ollame - `format="json"`), a nastepnie kod wywoluje dedykowane narzedzie (tool) odpowiedzialne za wyslanie wiadomosci e-mail.

Odpowiedz modelu jest walidowana przez Pydantic (`Literal` ograniczajacy dozwolone adresy dzialow) - jesli model zwroci niepoprawny lub nieznany adres, zgloszenie trafia bezpiecznie do fallbacku `other@example.com` zamiast przerywac dzialanie API bledem.

### Decyzja architektoniczna: sposob wywolania tool/function calling

Pierwotna implementacja korzystala z natywnego mechanizmu `bind_tools()` w LangChain, w ktorym to model samodzielnie decyduje, czy i kiedy wywolac narzedzie (`tool_calls`). W testach na lokalnych, malych modelach (Ollama, CPU) mechanizm ten okazal sie niewystarczajaco niezawodny - model czesto w ogole nie wywolywal narzedzia (odpowiadal samym tekstem), a w niektorych przypadkach generowal odpowiedz w nieskonczonosc, nie konczac zadania.

Aby zapewnic powtarzalne, poprawne dzialanie PoC, zastosowano nastepujace podejscie: model zwraca wylacznie ustrukturyzowana decyzje (`department_email`) w formacie JSON, ktorego poprawnosc jest gramatycznie wymuszana przez Ollame (`format="json"`) - to duzo bardziej niezawodny mechanizm niz poleganie na tym, czy model "zdecyduje sie" wywolac narzedzie. Na podstawie tej decyzji **kod aplikacji wywoluje dedykowane narzedzie** `send_department_email` (zdefiniowane przez dekorator `@tool` z LangChain), ktore faktycznie wysyla e-mail.

Agent w dalszym ciagu w pelni odpowiada za analize tresci zgloszenia i decyzje o dziale docelowym - jedyna zmiana dotyczy mechanizmu przekazania tej decyzji do wywolania narzedzia (ustrukturyzowany JSON zamiast natywnego `tool_calls`). Przy uzyciu wiekszych modeli (np. hostowanych w chmurze, nie lokalnie na CPU) natywny `tool_calls` dzialalby dla tej samej logiki biznesowej bez zmian w pozostalej czesci kodu - zmianie ulegloby jedynie kilka linii w `agent.py`.

## Uruchomienie

```bash
docker compose up -d
```

Srodowisko uruchamia sie w pelni automatycznie: kontener `ollama` startuje, healthcheck potwierdza jego gotowosc, serwis `ollama-init` pobiera wagi modelu (`qwen2.5:1.5b`, ~1GB), a dopiero po jego pomyslnym zakonczeniu startuje `api`. Nie sa wymagane zadne dodatkowe komendy - po `docker compose up -d` srodowisko jest w pelni gotowe do przyjmowania requestow (pierwsze uruchomienie potrwa dluzej ze wzgledu na pobieranie obrazu i modelu).

Wybrano model `qwen2.5:1.5b` (~1GB) jako kompromis miedzy szybkoscia dzialania na CPU a niezawodnoscia klasyfikacji zgloszen.

Dostepne sa wtedy:

| Adres                             | Opis          |
| --------------------------------- | ------------- |
| http://localhost:8000/api/v1/docs | Swagger UI    |
| http://localhost:8025             | Panel MailHog |
| http://localhost:11434            | Ollama        |

## Przykladowe wywolanie API

**Linux / macOS:**

```bash
curl -X POST http://localhost:8000/api/v1/support \
-H "Content-Type: application/json" \
-d '{
  "email":"jan@example.com",
  "subject":"Awaria komputera",
  "message":"Nie dziala mi komputer, ekran jest czarny i nie moge sie zalogowac."
}'
```

**Windows / PowerShell** - domyslny alias `curl` wskazuje na `Invoke-WebRequest` i inaczej obsluguje cudzyslowy. Dziala jedna z ponizszych wersji:

```powershell
# Opcja 1: curl.exe z JSON zapisanym do pliku (omija problemy z cudzyslowami)
'{"email":"jan@example.com","subject":"Awaria komputera","message":"Nie dziala mi komputer."}' | Out-File -Encoding utf8 body.json -NoNewline
curl.exe -X POST http://localhost:8000/api/v1/support -H "Content-Type: application/json" -d "@body.json"
```

```powershell
# Opcja 2: natywny PowerShell (Invoke-RestMethod)
$body = @{
    email   = "jan@example.com"
    subject = "Awaria komputera"
    message = "Nie dziala mi komputer, ekran jest czarny i nie moge sie zalogowac."
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/support" `
  -Method Post -ContentType "application/json" -Body $body
```

**Windows / cmd.exe (Wiersz polecen)** - inna skladnia niz PowerShell, `Out-File` tam nie dziala. Uzyj `echo` do zapisu pliku:

```cmd
echo {"email":"jan@example.com","subject":"Awaria komputera","message":"Nie dziala mi komputer."} > body.json
curl.exe -X POST http://localhost:8000/api/v1/support -H "Content-Type: application/json" -d "@body.json"
```

> Uwaga: upewnij sie, ze jestes we wlasciwym terminalu - PowerShell ma w prompcie prefiks `PS`, np. `PS C:\...>`, a cmd.exe nie, np. `C:\...>`. Komendy z jednej powloki najczesciej nie dzialaja w drugiej.

> **Alternatywnie (rekomendowane na Windows): Swagger UI**, bo omija wszystkie problemy z cudzyslowami w terminalu:
>
> 1. Otworz w przegladarce `http://localhost:8000/api/v1/docs`.
> 2. Rozwin sekcje `POST /api/v1/support` (klikni na nia).
> 3. Kliknij przycisk **"Try it out"** w prawym gornym rogu sekcji.
> 4. W polu tekstowym "Request body" wklej/zamien przykladowy JSON, np.:
>    ```json
>    {
>      "email": "jan@example.com",
>      "subject": "Awaria komputera",
>      "message": "Nie dziala mi komputer, ekran jest czarny i nie moge sie zalogowac."
>    }
>    ```
> 5. Kliknij niebieski przycisk **"Execute"**.
> 6. Wynik zobaczysz nizej w sekcji "Server response" - kod `200` oraz "Response body" z `department_email`.
> 7. Sprawdz MailHog (`http://localhost:8025`), czy pojawila sie tam nowa wiadomosc.

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
│   ├── agent.py       # Agent AI (LangChain + Ollama) - analiza i decyzja o dziale
│   └── mailer.py      # wysylka e-maili przez SMTP (MailHog)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```
