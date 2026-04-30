"""
OCR helpers backed by Tesseract.
"""

from __future__ import annotations

import asyncio
import io
import re

from app.config import OCR_LANG, TESSERACT_CMD


def _score_text(text: str) -> int:
    if not text:
        return 0
    cleaned = re.sub(r"\s+", "", text)
    useful = re.findall(r"[0-9A-Za-z가-힣]", cleaned)
    return len(useful)


def _prepare_variants(image):
    from PIL import ImageFilter, ImageOps

    image = ImageOps.exif_transpose(image)
    grayscale = ImageOps.grayscale(image)
    grayscale = ImageOps.autocontrast(grayscale)

    width, height = grayscale.size
    longest = max(width, height)
    if longest and longest < 1800:
        scale = 1800 / float(longest)
        grayscale = grayscale.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            resample=grayscale.Resampling.LANCZOS,
        )

    sharpened = grayscale.filter(ImageFilter.SHARPEN)
    denoised = sharpened.filter(ImageFilter.MedianFilter(size=3))
    thresholded = denoised.point(lambda px: 255 if px > 160 else 0, mode="1").convert("L")

    return [grayscale, denoised, thresholded]


def _ocr_sync(image_bytes: bytes) -> str:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise RuntimeError("Pillow is not installed. Please install OCR dependencies.") from exc

    try:
        import pytesseract
        from pytesseract import TesseractNotFoundError
    except ImportError as exc:
        raise RuntimeError("pytesseract is not installed. Please install OCR dependencies.") from exc

    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            best_text = ""
            best_score = -1
            variants = _prepare_variants(image)
            configs = [
                "--oem 3 --psm 6",
                "--oem 3 --psm 11",
                "--oem 3 --psm 4",
            ]

            for variant in variants:
                for config in configs:
                    text = pytesseract.image_to_string(variant, lang=OCR_LANG, config=config).strip()
                    score = _score_text(text)
                    if score > best_score:
                        best_score = score
                        best_text = text
    except UnidentifiedImageError as exc:
        raise ValueError("The uploaded file is not a readable image.") from exc
    except TesseractNotFoundError as exc:
        raise RuntimeError("Tesseract OCR is not installed or not found in PATH.") from exc
    except OSError as exc:
        raise ValueError("The uploaded image could not be opened.") from exc

    return best_text.strip()


async def extract_ocr_text(image_bytes: bytes) -> str:
    return await asyncio.to_thread(_ocr_sync, image_bytes)
