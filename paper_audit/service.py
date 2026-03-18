from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Callable

from .analyzer import (
    build_expected_title,
    build_invalid_reason,
    excerpt_text,
    is_valid_match,
    listed_title,
    score_page_text,
)
from .models import InvalidPaper, PaperListing, ScanResult, ScanSummary, utc_now
from .ocr import extract_page_texts
from .scraper import ExamCookerScraper
from .settings import AuditSettings
from .utils import read_json, slugify, write_json


class AuditService:
    def __init__(self, settings: AuditSettings, paths, scraper: ExamCookerScraper | None = None):
        self.settings = settings
        self.paths = paths
        self.scraper = scraper or ExamCookerScraper(settings)

    def load_latest_results(self) -> dict | None:
        return read_json(self.paths.latest_result_path)

    def _pdf_cache_path(self, paper: PaperListing) -> Path:
        file_name = f"{paper.paper_id}-{slugify(paper.course_code)}.pdf"
        return self.paths.pdf_dir / file_name

    def _load_pdf_bytes(self, paper: PaperListing, file_url: str) -> tuple[bytes, Path]:
        cache_path = self._pdf_cache_path(paper)
        if cache_path.exists():
            return cache_path.read_bytes(), cache_path

        pdf_bytes = self.scraper.download_pdf(file_url)
        cache_path.write_bytes(pdf_bytes)
        return pdf_bytes, cache_path

    def _inspect_paper(self, paper: PaperListing) -> InvalidPaper | None:
        detail = self.scraper.fetch_paper_detail(paper)
        pdf_bytes, cache_path = self._load_pdf_bytes(paper, detail.file_url)
        page_texts = extract_page_texts(
            pdf_bytes,
            max_pages=self.settings.max_title_pages,
            dpi=self.settings.render_dpi,
            lang=self.settings.tesseract_lang,
        )

        if not page_texts:
            best_result = score_page_text(0, "", paper)
        else:
            scored_pages = [
                score_page_text(page_index=page_index, page_text=page_text, listing=paper)
                for page_index, page_text in enumerate(page_texts)
            ]
            valid_pages = [
                result
                for result in scored_pages
                if is_valid_match(
                    result,
                    threshold=self.settings.title_match_threshold,
                    partial_threshold=self.settings.title_partial_threshold,
                )
            ]
            if valid_pages:
                return None
            best_result = max(scored_pages, key=lambda result: result.overall_score)

        return InvalidPaper(
            paper_id=paper.paper_id,
            subject_title=paper.subject_title,
            course_code=paper.course_code,
            exam_type=paper.exam_type,
            slot=paper.slot,
            year=paper.year,
            website_url=paper.website_url,
            pdf_url=detail.file_url,
            listed_title=listed_title(paper),
            ocr_title=best_result.candidate_title or "No reliable title extracted",
            match_score=round(best_result.overall_score, 3),
            ocr_page=best_result.page_index + 1,
            reason=build_invalid_reason(best_result),
            page_excerpt=excerpt_text(best_result.page_text),
            cache_path=str(cache_path),
        )

    def _build_error_result(self, paper: PaperListing, error: Exception) -> InvalidPaper:
        return InvalidPaper(
            paper_id=paper.paper_id,
            subject_title=paper.subject_title,
            course_code=paper.course_code,
            exam_type=paper.exam_type,
            slot=paper.slot,
            year=paper.year,
            website_url=paper.website_url,
            pdf_url="",
            listed_title=listed_title(paper),
            ocr_title="No OCR result",
            match_score=0.0,
            ocr_page=0,
            reason=f"Failed to inspect the paper: {error}",
            page_excerpt="",
            cache_path="",
        )

    def run_scan(
        self,
        limit: int | None = None,
        progress: Callable[[dict], None] | None = None,
    ) -> ScanResult:
        progress = progress or (lambda _event: None)

        started_at = utc_now()
        listings, total_listing_pages = self.scraper.fetch_all_listings(
            limit=limit,
            progress=lambda message: progress({"stage": "listing", "message": message})
        )

        if limit is not None:
            listings = listings[:limit]

        invalid_papers: list[InvalidPaper] = []
        checked_papers = 0
        lock = Lock()

        with ThreadPoolExecutor(max_workers=self.settings.max_paper_workers) as executor:
            futures = {executor.submit(self._inspect_paper, paper): paper for paper in listings}
            for future in as_completed(futures):
                paper = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    result = self._build_error_result(paper, exc)
                with lock:
                    checked_papers += 1
                    if result:
                        invalid_papers.append(result)
                progress(
                    {
                        "stage": "papers",
                        "paper_id": paper.paper_id,
                        "checked": checked_papers,
                        "total": len(listings),
                        "invalid": len(invalid_papers),
                    }
                )

        invalid_papers.sort(key=lambda paper: (paper.subject_title.lower(), paper.year, paper.slot))
        summary = ScanSummary(
            generated_at=utc_now(),
            started_at=started_at,
            finished_at=utc_now(),
            total_listing_pages=total_listing_pages,
            total_papers=len(listings),
            checked_papers=checked_papers,
            invalid_papers=len(invalid_papers),
            max_pages_scanned=self.settings.max_title_pages,
        )
        result = ScanResult(summary=summary, invalid_papers=invalid_papers)
        write_json(self.paths.latest_result_path, result.to_dict())
        return result
