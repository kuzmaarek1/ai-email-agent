from fastapi import FastAPI

# Model użyty przez Agenta AI (podłączonego do lokalnej Ollamy)
OLLAMA_MODEL = "qwen2.5:0.5b"

app = FastAPI(
    title="AI Support API",
    docs_url="/api/v1/docs",
)


@app.get("/")
async def root():
    return {"message": "Hello World"}