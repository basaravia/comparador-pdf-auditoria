from fastapi import FastAPI

app = FastAPI(title="Comparador de PDFs — Auditoría")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
