from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import ScanPaths


@dataclass(slots=True)
class AuditSettings:
    base_url: str = "https://examcooker.acmvit.in"
    listing_path: str = "/past_papers"
    request_timeout: float = 30.0
    max_listing_workers: int = 4
    max_paper_workers: int = 3
    max_title_pages: int = 1
    render_dpi: int = 220
    gemini_model: str = "gemini-3-pro-preview"
    gemini_api_version: str = "v1alpha"


def load_settings(root: Path | None = None) -> tuple[AuditSettings, ScanPaths]:
    resolved_root = root or Path(__file__).resolve().parent.parent
    return AuditSettings(), ScanPaths.build(resolved_root)
