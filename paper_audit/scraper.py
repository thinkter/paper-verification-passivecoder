from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .models import PaperDetail, PaperListing
from .settings import AuditSettings


TOTAL_PAGES_RE = re.compile(r'\\?"totalPages\\?":(\d+)')
FILE_URL_RE = re.compile(r'\\?"fileUrl\\?":\\?"([^"]+\.pdf)')
POSTED_AT_RE = re.compile(r"Posted at:\s*<!-- -->.*?<!-- -->,\s*<!-- -->(\d+<!-- -->-<!-- -->\d+<!-- -->-<!-- -->\d+)", re.DOTALL)


@dataclass(slots=True)
class ExamCookerScraper:
    settings: AuditSettings

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.settings.base_url,
            timeout=self.settings.request_timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "paper-audit/0.1 (+https://examcooker.acmvit.in)",
            },
        )

    def fetch_listing_page(self, client: httpx.Client, page_number: int) -> tuple[list[PaperListing], int | None]:
        response = client.get(self.settings.listing_path, params={"page": page_number} if page_number > 1 else None)
        response.raise_for_status()
        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        papers: list[PaperListing] = []
        seen_ids: set[str] = set()

        for anchor in soup.select('a[href^="/past_papers/"]'):
            href = anchor.get("href", "")
            if not re.fullmatch(r"/past_papers/[a-z0-9]+", href):
                continue
            paper_id = href.rsplit("/", 1)[-1]
            if paper_id in seen_ids:
                continue

            title_node = anchor.select_one("div.mb-1")
            meta_node = anchor.select_one("div.text-xs")
            if not title_node or not meta_node:
                continue

            meta_parts = [part.strip() for part in meta_node.get_text(" ", strip=True).split("|")]
            if len(meta_parts) != 4:
                continue

            exam_type = meta_parts[0]
            slot = meta_parts[1].replace("Slot ", "")
            year = meta_parts[2]
            course_code = meta_parts[3]

            papers.append(
                PaperListing(
                    paper_id=paper_id,
                    subject_title=title_node.get_text(" ", strip=True),
                    exam_type=exam_type,
                    slot=slot,
                    year=year,
                    course_code=course_code,
                    website_url=urljoin(self.settings.base_url, href),
                    page_number=page_number,
                )
            )
            seen_ids.add(paper_id)

        total_pages = self._extract_total_pages(html)
        return papers, total_pages

    def fetch_all_listings(
        self,
        limit: int | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> tuple[list[PaperListing], int]:
        progress = progress or (lambda _: None)
        listings: list[PaperListing] = []

        with self._client() as client:
            first_page_papers, total_pages = self.fetch_listing_page(client, 1)
            listings.extend(first_page_papers)
            page_count = total_pages or 1

            if limit is not None and first_page_papers:
                page_size = len(first_page_papers)
                page_count = min(page_count, max(1, -(-limit // page_size)))

            progress(f"Loaded listing page 1/{page_count}")

            if page_count > 1:
                with ThreadPoolExecutor(max_workers=self.settings.max_listing_workers) as executor:
                    futures = {
                        executor.submit(self.fetch_listing_page, client, page_number): page_number
                        for page_number in range(2, page_count + 1)
                    }
                    for future in as_completed(futures):
                        page_number = futures[future]
                        page_papers, _ = future.result()
                        listings.extend(page_papers)
                        progress(f"Loaded listing page {page_number}/{page_count}")

        listings.sort(key=lambda paper: (paper.page_number, paper.paper_id))
        return listings, page_count

    def fetch_paper_detail(self, paper: PaperListing) -> PaperDetail:
        with self._client() as client:
            response = client.get(paper.website_url)
            response.raise_for_status()
            html = response.text

        file_url = self._extract_file_url(html)
        if not file_url:
            raise ValueError(f"Could not find fileUrl for paper {paper.paper_id}")

        posted_match = POSTED_AT_RE.search(html)
        posted_at = posted_match.group(1) if posted_match else None

        return PaperDetail(file_url=file_url, posted_at=posted_at)

    def download_pdf(self, file_url: str) -> bytes:
        with self._client() as client:
            response = client.get(file_url)
            response.raise_for_status()
            return response.content

    @staticmethod
    def _extract_total_pages(html: str) -> int | None:
        match = TOTAL_PAGES_RE.search(html)
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def _extract_file_url(html: str) -> str | None:
        match = FILE_URL_RE.search(html)
        if not match:
            return None
        return match.group(1)
