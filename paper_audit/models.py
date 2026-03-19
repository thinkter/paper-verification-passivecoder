from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class PaperListing:
    paper_id: str
    subject_title: str
    exam_type: str
    slot: str
    year: str
    course_code: str
    website_url: str
    page_number: int


@dataclass(slots=True)
class PaperDetail:
    file_url: str
    posted_at: str | None = None


@dataclass(slots=True)
class InvalidPaper:
    paper_id: str
    subject_title: str
    course_code: str
    exam_type: str
    slot: str
    year: str
    website_url: str
    pdf_url: str
    listed_title: str
    detected_title: str
    match_score: float
    checked_page: int
    reason: str
    page_excerpt: str
    cache_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScanSummary:
    generated_at: str
    started_at: str
    finished_at: str
    total_listing_pages: int
    total_papers: int
    checked_papers: int
    invalid_papers: int
    max_pages_scanned: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ScanResult:
    summary: ScanSummary
    invalid_papers: list[InvalidPaper] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary.to_dict(),
            "invalid_papers": [paper.to_dict() for paper in self.invalid_papers],
        }


@dataclass(slots=True)
class ScanPaths:
    root: Path
    cache_dir: Path
    pdf_dir: Path
    results_dir: Path
    latest_result_path: Path

    @classmethod
    def build(cls, root: Path) -> "ScanPaths":
        data_root = root / "data"
        cache_dir = data_root / "cache"
        pdf_dir = cache_dir / "pdfs"
        results_dir = data_root / "results"
        latest_result_path = results_dir / "latest_results.json"

        for path in (cache_dir, pdf_dir, results_dir):
            path.mkdir(parents=True, exist_ok=True)

        return cls(
            root=root,
            cache_dir=cache_dir,
            pdf_dir=pdf_dir,
            results_dir=results_dir,
            latest_result_path=latest_result_path,
        )


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
