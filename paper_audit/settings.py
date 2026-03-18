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
    max_title_pages: int = 4
    render_dpi: int = 300
    tesseract_lang: str = "eng"
    title_match_threshold: float = 0.72
    title_partial_threshold: float = 0.54


def load_settings(root: Path | None = None) -> tuple[AuditSettings, ScanPaths]:
    resolved_root = root or Path(__file__).resolve().parent.parent
    return AuditSettings(), ScanPaths.build(resolved_root)
