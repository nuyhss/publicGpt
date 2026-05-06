"""
OCR helpers backed by Tesseract.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import re
import subprocess
import tempfile
from pathlib import Path

from app.config import (
    OCR_LANG,
    OCR_PDF_DPI,
    OCR_PDF_MAX_PAGES,
    OCR_VISION_FALLBACK,
    OCR_VISION_MIN_SCORE,
    OCR_VISION_MODEL,
    TESSERACT_CMD,
)
from app.core.llm import call_llm_with_image, get_response_text

logger = logging.getLogger("publicgpt.ocr")


def _score_text(text: str) -> int:
    if not text:
        return 0
    cleaned = re.sub(r"\s+", "", text)
    useful = re.findall(r"[0-9A-Za-z가-힣]", cleaned)
    return len(useful)


def _prepare_variants(image):
    from PIL import Image, ImageFilter, ImageOps

    image = ImageOps.exif_transpose(image)
    grayscale = ImageOps.grayscale(image)
    grayscale = ImageOps.autocontrast(grayscale)

    width, height = grayscale.size
    longest = max(width, height)
    if longest and longest < 1800:
        scale = 1800 / float(longest)
        resample_filter = getattr(Image, "LANCZOS", getattr(Image, "BICUBIC", 3))
        grayscale = grayscale.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            resample=resample_filter,
        )

    sharpened = grayscale.filter(ImageFilter.SHARPEN)
    denoised = sharpened.filter(ImageFilter.MedianFilter(size=3))
    thresholded = denoised.point(lambda px: 255 if px > 160 else 0, mode="1").convert("L")

    return [grayscale, denoised, thresholded]


def _image_to_data_url(image) -> str:
    prepared = image.convert("RGB")
    buf = io.BytesIO()
    prepared.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _should_try_vision(best_text: str, best_score: int) -> bool:
    if not OCR_VISION_FALLBACK:
        return False
    if best_score < OCR_VISION_MIN_SCORE:
        return True
    lowered = best_text.lower()
    if lowered.count("?") >= 3:
        return True
    return False


def _vision_ocr_sync(image) -> str:
    prompt = (
        "Extract all readable text from this image exactly as written. "
        "Preserve line breaks when helpful. "
        "Do not summarize, translate, or explain. "
        "If only part of the text is readable, return only the readable text."
    )
    result = call_llm_with_image(
        prompt=prompt,
        image_url=_image_to_data_url(image),
        model=OCR_VISION_MODEL,
        max_tokens=800,
    )
    return get_response_text(result).strip()


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

            if _should_try_vision(best_text, best_score):
                try:
                    vision_text = _vision_ocr_sync(image)
                    vision_score = _score_text(vision_text)
                    if vision_score >= best_score:
                        best_text = vision_text
                        best_score = vision_score
                except Exception as exc:
                    logger.warning("Vision OCR fallback failed: %s", exc)
    except UnidentifiedImageError as exc:
        raise ValueError("The uploaded file is not a readable image.") from exc
    except TesseractNotFoundError as exc:
        raise RuntimeError("Tesseract OCR is not installed or not found in PATH.") from exc
    except OSError as exc:
        raise ValueError("The uploaded image could not be opened.") from exc

    return best_text.strip()


def _extract_pdf_ocr_sync(pdf_bytes: bytes) -> str:
    with tempfile.TemporaryDirectory(prefix="publicgpt-pdf-ocr-") as tmpdir:
        tmp_path = Path(tmpdir)
        pdf_path = tmp_path / "input.pdf"
        output_prefix = tmp_path / "page"
        pdf_path.write_bytes(pdf_bytes)

        cmd = [
            "pdftoppm",
            "-png",
            "-r",
            str(OCR_PDF_DPI),
            "-f",
            "1",
            "-l",
            str(OCR_PDF_MAX_PAGES),
            str(pdf_path),
            str(output_prefix),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise RuntimeError("pdftoppm is not installed, so PDF OCR is unavailable.") from exc
        except subprocess.CalledProcessError as exc:
            error_text = (exc.stderr or exc.stdout or "").strip()
            raise ValueError(f"The uploaded PDF could not be converted for OCR. {error_text}".strip()) from exc

        page_texts: list[str] = []
        for image_path in sorted(tmp_path.glob("page-*.png")):
            text = _ocr_sync(image_path.read_bytes()).strip()
            if text:
                page_texts.append(f"[Page {len(page_texts) + 1}]\n{text}")

        return "\n\n".join(page_texts).strip()


async def extract_ocr_text(file_bytes: bytes, content_type: str = "image/png") -> str:
    normalized = (content_type or "").lower()
    if normalized == "application/pdf":
        return await asyncio.to_thread(_extract_pdf_ocr_sync, file_bytes)
    return await asyncio.to_thread(_ocr_sync, file_bytes)
