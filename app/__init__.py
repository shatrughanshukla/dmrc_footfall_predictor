from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="MetroInsights",
    description="DMRC passenger-demand and service-planning prototype",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None,
)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

from app import routes  # noqa: E402,F401
