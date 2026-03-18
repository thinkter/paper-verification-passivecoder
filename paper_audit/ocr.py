from __future__ import annotations

from io import BytesIO

import fitz
import pytesseract
from PIL import Image, ImageFilter, ImageOps

Image.MAX_IMAGE_PIXELS = None


def _preprocess_image(image: Image.Image) -> Image.Image:
    
    grayscale = ImageOps.grayscale(image)
    autocontrast = ImageOps.autocontrast(grayscale)
    sharpened = autocontrast.filter(ImageFilter.SHARPEN)
    return sharpened


def extract_page_texts(pdf_bytes: bytes, max_pages: int, dpi: int, lang: str) -> list[str]:
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    texts: list[str] = []

    try:
        page_limit = min(max_pages, document.page_count)
        scale = dpi / 72
        matrix = fitz.Matrix(scale, scale)

        for page_index in range(page_limit):
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.open(BytesIO(pixmap.tobytes("png")))
            processed = _preprocess_image(image)
            text = pytesseract.image_to_string(
                processed,
                lang=lang,
                config="--oem 1 --psm 6",
            )
            texts.append(text)
    finally:
        document.close()

    return texts
