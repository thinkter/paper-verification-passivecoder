from __future__ import annotations

import re

from rapidfuzz import fuzz

from .models import OcrResult, PaperListing
from .utils import compact_text, normalize_text


NOISE_PATTERNS = (
    "vellore institute of technology",
    "time:",
    "max marks",
    "registered number",
    "answer all questions",
    "programme",
    "school of",
    "semester",
    "assessment",
    "marks:",
)
COURSE_LINE_RE = re.compile(r"(course|ourse).*(name|code)|subject", re.IGNORECASE)
CODE_TOKEN_RE = re.compile(r"[A-Z0-9]{6,12}")


def listed_title(listing: PaperListing) -> str:
    return (
        f"{listing.subject_title} [{listing.course_code}] "
        f"{listing.exam_type} {listing.slot} {listing.year}"
    )


def build_expected_title(listing: PaperListing) -> str:
    return f"{listing.subject_title} {listing.course_code}"


def extract_candidate_title(page_text: str, listing: PaperListing) -> str:
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    if not lines:
        return ""

    for index, line in enumerate(lines[:25]):
        if COURSE_LINE_RE.search(line):
            tail = re.split(r"[:\-]", line, maxsplit=1)[-1].strip()
            if "," in tail:
                tail = tail.split(",", 1)[-1].strip()
            pieces = [tail] if tail else []
            if index + 1 < len(lines) and len(normalize_text(tail)) < 6:
                pieces.append(lines[index + 1].strip())
            candidate = " ".join(piece for piece in pieces if piece).strip()
            if len(normalize_text(candidate)) >= 4:
                return candidate[:220]

    cleaned_lines = []
    expected_norm = normalize_text(listing.subject_title)
    expected_code = listing.course_code.upper()

    for line in lines[:20]:
        line_norm = normalize_text(line)
        if len(line_norm) < 4:
            continue
        if any(pattern in line_norm for pattern in NOISE_PATTERNS):
            continue
        if expected_code in line.upper():
            cleaned_lines.append(line)
            continue
        if fuzz.partial_ratio(line_norm, expected_norm) >= 55:
            cleaned_lines.append(line)
            continue
        if len(cleaned_lines) < 3:
            cleaned_lines.append(line)

    if not cleaned_lines:
        cleaned_lines = lines[:3]

    title = " ".join(cleaned_lines[:3])
    title = re.sub(r"\s+", " ", title).strip()
    return title[:220]


def score_page_text(page_index: int, page_text: str, listing: PaperListing) -> OcrResult:
    candidate_title = extract_candidate_title(page_text, listing)
    expected_title = build_expected_title(listing)

    normalized_candidate = normalize_text(candidate_title or page_text)
    normalized_page = normalize_text(page_text)
    normalized_expected = normalize_text(expected_title)
    normalized_subject = normalize_text(listing.subject_title)

    title_score = fuzz.partial_ratio(normalized_expected, normalized_candidate) / 100
    page_title_score = fuzz.partial_ratio(normalized_subject, normalized_page) / 100
    token_score = fuzz.token_set_ratio(normalized_expected, normalized_page) / 100
    code_score = course_code_score(page_text, listing.course_code)
    code_found = code_score >= 0.8
    exam_type_found = listing.exam_type.upper().replace("-", "") in page_text.upper().replace("-", "")

    overall_score = (
        (title_score * 0.35)
        + (page_title_score * 0.35)
        + (token_score * 0.15)
        + (0.15 * code_score)
        + (0.05 if exam_type_found else 0.0)
    )

    return OcrResult(
        page_index=page_index,
        candidate_title=candidate_title,
        page_text=page_text,
        title_score=title_score,
        page_title_score=page_title_score,
        token_score=token_score,
        code_found=code_found,
        code_score=code_score,
        exam_type_found=exam_type_found,
        overall_score=overall_score,
    )


def course_code_score(page_text: str, course_code: str) -> float:
    uppercase_text = page_text.upper()
    expected = course_code.upper()

    if expected in uppercase_text:
        return 1.0

    best = 0.0
    for token in CODE_TOKEN_RE.findall(uppercase_text):
        score = fuzz.ratio(expected, token) / 100
        if score > best:
            best = score
    return best


def is_valid_match(result: OcrResult, threshold: float, partial_threshold: float) -> bool:
    if result.overall_score >= threshold:
        return True
    if result.page_title_score >= 0.8:
        return True
    if result.code_score >= 0.9 and result.page_title_score >= 0.45:
        return True
    if result.code_score >= 0.75 and result.page_title_score >= 0.5:
        return True
    if result.code_found and result.title_score >= partial_threshold:
        return True
    if result.page_title_score >= 0.68 and result.token_score >= partial_threshold:
        return True
    return False


def build_invalid_reason(result: OcrResult) -> str:
    if not result.page_text.strip():
        return "No OCR text could be extracted from the title pages."
    if result.code_score < 0.6:
        return "The course code was not found on the best-matching title page."
    return "The OCR title does not match the website label closely enough."


def excerpt_text(text: str, limit: int = 200) -> str:
    excerpt = " ".join(text.split())
    return excerpt[:limit] + ("..." if len(excerpt) > limit else "")
