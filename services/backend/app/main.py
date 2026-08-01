from fastapi import FastAPI

from app.config import get_settings

app = FastAPI(
    title="KSPDB Fault Localization API",
    version="0.1.0",
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "backend",
        "environment": settings.app_env,
    }
