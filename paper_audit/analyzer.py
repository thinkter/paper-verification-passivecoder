from __future__ import annotations

from .models import PaperListing


def listed_title(listing: PaperListing) -> str:
    return (
        f"{listing.subject_title} [{listing.course_code}] "
        f"{listing.exam_type} {listing.slot} {listing.year}"
    )
