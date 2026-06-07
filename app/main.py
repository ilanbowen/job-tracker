from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes import job_applications

app = FastAPI(title=settings.app_name)

Path(settings.logo_dir).mkdir(parents=True, exist_ok=True)

LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def _safe_logo_name(filename: str) -> str:
    clean = Path(filename).name
    if clean != filename or Path(clean).suffix.lower() not in LOGO_EXTENSIONS:
        raise HTTPException(status_code=404, detail="Logo not found")
    return clean


@app.get("/logos/{filename}")
def logo_file(filename: str):
    clean = _safe_logo_name(filename)
    for directory in (Path(settings.logo_dir), Path(settings.seed_logo_dir)):
        path = directory / clean
        if path.is_file():
            return FileResponse(path)
    raise HTTPException(status_code=404, detail="Logo not found")


app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(job_applications.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}
