from __future__ import annotations

import json
import os
from dataclasses import dataclass

import fitz
from google import genai
from google.genai import types

from .models import PaperListing


MODEL_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "matches_metadata": {"type": "boolean"},
        "confidence": {"type": "number"},
        "extracted_title": {"type": "string"},
        "extracted_course_code": {"type": "string"},
        "extracted_exam_type": {"type": "string"},
        "extracted_slot": {"type": "string"},
        "extracted_year": {"type": "string"},
        "mismatch_reason": {"type": "string"},
        "page_summary": {"type": "string"},
    },
    "required": [
        "matches_metadata",
        "confidence",
        "extracted_title",
        "extracted_course_code",
        "extracted_exam_type",
        "extracted_slot",
        "extracted_year",
        "mismatch_reason",
        "page_summary",
    ],
}


@dataclass(slots=True)
class VerificationDecision:
    extracted_title: str
    extracted_course_code: str
    extracted_exam_type: str
    extracted_slot: str
    extracted_year: str
    matches_metadata: bool
    confidence: float
    mismatch_reason: str
    page_summary: str
    page_excerpt: str
    checked_page: int = 1


def _build_prompt(listing: PaperListing) -> str:
    metadata = {
        "subject_title": listing.subject_title,
        "course_code": listing.course_code,
        "exam_type": listing.exam_type,
        "slot": listing.slot,
        "year": listing.year,
    }
    return (
        "You are checking whether the first page of an exam paper matches the website metadata.\n"
        "Look only at the attached first-page image.\n"
        "Extract the visible title and paper details, then decide whether the page matches the metadata.\n"
        "Be strict about course code mismatches.\n"
        "Return JSON only.\n\n"
        f"Website metadata:\n{json.dumps(metadata, indent=2)}\n\n"
        "Interpretation rules:\n"
        "- matches_metadata must be true only if the first page clearly refers to the same subject/paper.\n"
        "- confidence must be between 0 and 1.\n"
        "- mismatch_reason should be empty when matches_metadata is true.\n"
        "- page_summary should be a concise summary of what is visible on page 1.\n"
    )


def extract_first_page(pdf_bytes: bytes, dpi: int) -> tuple[bytes, str]:
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if document.page_count == 0:
            raise ValueError("The PDF has no pages.")

        page = document.load_page(0)
        scale = dpi / 72
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        page_text = page.get_text("text").strip()
        return pixmap.tobytes("png"), page_text
    finally:
        document.close()


class GeminiPaperVerifier:
    def __init__(self, settings) -> None:
        self.settings = settings

    def ensure_ready(self) -> None:
        if self._api_key() is None:
            raise RuntimeError(
                "Missing Gemini API key. Set GEMINI_API_KEY or GOOGLE_API_KEY before running a scan."
            )

    def verify_first_page(self, pdf_bytes: bytes, listing: PaperListing) -> VerificationDecision:
        page_image, page_text = extract_first_page(pdf_bytes, dpi=self.settings.render_dpi)

        with self._build_client() as client:
            response = client.models.generate_content(
                model=self.settings.gemini_model,
                contents=[
                    types.Part.from_text(text=_build_prompt(listing)),
                    types.Part.from_bytes(data=page_image, mime_type="image/png"),
                ],
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    response_json_schema=MODEL_RESPONSE_SCHEMA,
                    max_output_tokens=500,
                ),
            )

        parsed = response.parsed
        if parsed is None:
            try:
                parsed = json.loads(response.text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Gemini returned invalid JSON: {response.text!r}") from exc

        mismatch_reason = (parsed.get("mismatch_reason") or "").strip()
        matches_metadata = bool(parsed.get("matches_metadata"))
        if matches_metadata:
            mismatch_reason = ""

        return VerificationDecision(
            extracted_title=(parsed.get("extracted_title") or "").strip(),
            extracted_course_code=(parsed.get("extracted_course_code") or "").strip(),
            extracted_exam_type=(parsed.get("extracted_exam_type") or "").strip(),
            extracted_slot=(parsed.get("extracted_slot") or "").strip(),
            extracted_year=(parsed.get("extracted_year") or "").strip(),
            matches_metadata=matches_metadata,
            confidence=max(0.0, min(float(parsed.get("confidence") or 0.0), 1.0)),
            mismatch_reason=mismatch_reason,
            page_summary=(parsed.get("page_summary") or "").strip(),
            page_excerpt=excerpt_text(page_text or parsed.get("page_summary") or ""),
        )

    def _api_key(self) -> str | None:
        return os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

    def _build_client(self) -> genai.Client:
        api_key = self._api_key()
        if api_key is None:
            raise RuntimeError(
                "Missing Gemini API key. Set GEMINI_API_KEY or GOOGLE_API_KEY before running a scan."
            )
        return genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(api_version=self.settings.gemini_api_version),
        )


def excerpt_text(text: str, limit: int = 200) -> str:
    compact = " ".join(text.split())
    return compact[:limit] + ("..." if len(compact) > limit else "")
