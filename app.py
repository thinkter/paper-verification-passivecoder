from __future__ import annotations

from pathlib import Path
from threading import Lock, Thread
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from paper_audit.scraper import ExamCookerScraper
from paper_audit.service import AuditService
from paper_audit.settings import load_settings


class ScanState:
    def __init__(self) -> None:
        self.lock = Lock()
        self.status = "idle"
        self.message = "No scan has been run yet."
        self.progress: dict[str, Any] = {}
        self.error: str | None = None

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "status": self.status,
                "message": self.message,
                "progress": self.progress,
                "error": self.error,
            }

    def update(self, **fields: Any) -> None:
        with self.lock:
            for key, value in fields.items():
                setattr(self, key, value)


ROOT = Path(__file__).resolve().parent
settings, paths = load_settings(ROOT)
service = AuditService(settings=settings, paths=paths, scraper=ExamCookerScraper(settings))
scan_state = ScanState()

app = FastAPI(title="ExamCooker OCR Audit")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=str(ROOT / "templates"))


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"latest_results": service.load_latest_results()},
    )


@app.get("/api/results")
def get_results() -> dict[str, Any]:
    results = service.load_latest_results()
    return {
        "results": results,
        "scan": scan_state.snapshot(),
    }


@app.post("/api/scan")
def start_scan(limit: int | None = None) -> dict[str, Any]:
    snapshot = scan_state.snapshot()
    if snapshot["status"] == "running":
        raise HTTPException(status_code=409, detail="A scan is already running.")

    def background_job() -> None:
        try:
            scan_state.update(status="running", message="Fetching paper listings...", progress={}, error=None)
            service.run_scan(limit=limit, progress=lambda event: scan_state.update(message="Scanning papers...", progress=event))
            scan_state.update(status="completed", message="Scan complete.")
        except Exception as exc:  # noqa: BLE001
            scan_state.update(status="failed", message="Scan failed.", error=str(exc))

    Thread(target=background_job, daemon=True).start()
    return {"ok": True, "scan": scan_state.snapshot()}
