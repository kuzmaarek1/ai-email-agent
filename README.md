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

Agent dostaje narzedzie `send_department_email` poprzez natywny mechanizm `bind_tools()` z LangChain i **sam decyduje**, czy i z jakimi argumentami je wywolac (prawdziwy tool/function calling - `response.tool_calls`). To jest glowna sciezka dzialania aplikacji, zgodnie z wymogiem zadania. Szczegoly dotyczace niezawodnosci tego mechanizmu na malych, lokalnych modelach oraz zastosowanej sciezki zapasowej opisano w sekcji **Uwagi / znane ograniczenia**.

## Uruchomienie

```bash
docker compose up -d
```

Srodowisko uruchamia sie w pelni automatycznie: kontener `ollama` startuje, healthcheck potwierdza jego gotowosc, serwis `ollama-init` pobiera wagi modelu, a dopiero po jego pomyslnym zakonczeniu startuje `api`. Nie sa wymagane zadne dodatkowe komendy - po `docker compose up -d` srodowisko jest w pelni gotowe do przyjmowania requestow (pierwsze uruchomienie potrwa dluzej ze wzgledu na pobieranie obrazu i modelu).

Wybrano model `qwen2.5:1.5b` (~1GB) jako kompromis miedzy szybkoscia dzialania na CPU a rozmiarem obrazu. Model ten technicznie wspiera tool calling w Ollamie, jednak przy tak malym rozmiarze bywa niestabilny (stad opisana wyzej sciezka zapasowa). Jesli priorytetem jest wyzsza niezawodnosc natywnego `tool_calls` kosztem wiekszego pobrania i wolniejszego CPU inference, warto podmienic model na `qwen2.5:7b-instruct` lub `qwen3:4b` (zmiana w jednym miejscu - `ollama-init` w `docker-compose.yml` oraz zmienna `OLLAMA_MODEL`).

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
> 6. Wynik zobaczysz nizej w sekcji "Server response" - kod `200` oraz "Response body" z `department_email` i `routing_method`.
> 7. Sprawdz MailHog (`http://localhost:8025`), czy pojawila sie tam nowa wiadomosc.

## Przykladowa odpowiedz

```json
{
  "status": "success",
  "department_email": "it@example.com",
  "routing_method": "tool_calls"
}
```

Pole `routing_method` przyjmuje wartosc `"tool_calls"`, gdy model sam wywolal narzedzie (oczekiwana sciezka), lub `"fallback"`, gdy zadzialala sciezka zapasowa opisana w sekcji Uwagi / znane ograniczenia.

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
   - w odpowiedzi API pole `routing_method` ma wartosc `"tool_calls"` (potwierdza to, ze zadanie zostalo obsluzone przez natywny tool/function calling modelu, zgodnie z wymogiem zadania).

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

## Uwagi / znane ograniczenia

Zgodnie z wymogiem zadania, glowna sciezka aplikacji opiera sie na natywnym mechanizmie `bind_tools()` z LangChain, w ktorym model samodzielnie decyduje, czy i kiedy wywolac narzedzie `send_department_email` (`tool_calls`). Kod aplikacji jedynie odczytuje te decyzje i wysyla e-mail, nie podejmujac za model decyzji o docelowym dziale.

W testach na malym, lokalnym modelu (Ollama, CPU) mechanizm ten bywal niewystarczajaco niezawodny - model czasem nie wywolywal narzedzia, tylko odpowiadal samym tekstem. Na taki wypadek dodano sciezke zapasowa: jesli pierwsza proba nie zwroci `tool_calls`, wykonywane jest drugie wywolanie modelu z wymuszonym `format="json"`, sluzace juz wylacznie do klasyfikacji, a kod na tej podstawie recznie wywoluje narzedzie. Niepoprawna lub nieznana decyzja modelu (w kazdej sciezce) trafia do bezpiecznego fallbacku `other@example.com` (walidacja Pydantic `Literal`).

Odpowiedz API zawiera pole `routing_method` (`"tool_calls"` lub `"fallback"`), ktore jednoznacznie pokazuje, ktora sciezka obsluzyla dane zgloszenie - bez zagladania w logi.

Domyslny model to `qwen2.5:1.5b` - wybrany ze wzgledu na maly rozmiar i szybkie uruchomienie PoC, kosztem wiekszej podatnosci na fallback. Przy wiekszym modelu (np. `qwen2.5:7b-instruct` lub `qwen3:4b`) `tool_calls` dzialalby bardziej niezawodnie - zmiana ograniczylaby sie do podmiany nazwy modelu w `docker-compose.yml` i `OLLAMA_MODEL`.

Pozostale uwarunkowania: system dziala CPU-only (zgodnie z wymaganiami), co oznacza wolniejsza inferencje; Agent ma dostep tylko do jednego narzedzia, co upraszcza klasyfikacje dla malego modelu.
