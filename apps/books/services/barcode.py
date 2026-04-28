"""
Image-based barcode extraction service.

Uses pyzbar for barcode detection with PIL preprocessing.
This tier runs server-side only as a fallback when client-side detection fails,
using the same image but with stronger preprocessing (grayscale, auto-contrast,
and sharpening) that may outperform browser-side decoding on low-quality images.

System dependency: libzbar0 (libzbar-dev on Debian/Ubuntu; libzbar on macOS via brew).
If pyzbar is unavailable the function raises ImportError — callers should handle this.
"""

import logging
import re

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

_ISBN13_RE = re.compile(r"97[89]\d{10}")
_ISBN10_RE = re.compile(r"\d{9}[\dX]", re.IGNORECASE)


def _validate_isbn13(digits: str) -> bool:
    if not re.fullmatch(r"\d{13}", digits):
        return False
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:12]))
    return (10 - (total % 10)) % 10 == int(digits[12])


def _validate_isbn10(digits: str) -> bool:
    if not re.fullmatch(r"\d{9}[\dX]", digits, re.IGNORECASE):
        return False
    total = sum(
        (10 - i) * (10 if c.upper() == "X" else int(c)) for i, c in enumerate(digits)
    )
    return total % 11 == 0


def _isbn10_to_isbn13(isbn10: str) -> str | None:
    cleaned = isbn10.replace("-", "").replace(" ", "")
    if len(cleaned) != 10 or not _validate_isbn10(cleaned):
        return None
    base = "978" + cleaned[:9]
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(base))
    check = (10 - (total % 10)) % 10
    return base + str(check)


def _normalize_raw(raw: str) -> str | None:
    """Normalize a raw barcode or OCR digit string to a valid ISBN-13."""
    digits = re.sub(r"[\s\-]", "", raw.strip())
    if len(digits) == 13 and _validate_isbn13(digits):
        return digits
    if len(digits) == 10:
        return _isbn10_to_isbn13(digits)
    return None


def _preprocess_variants(pil_image: Image.Image) -> list[Image.Image]:
    """
    Return a list of preprocessed image variants to maximize barcode detection.
    Each variant applies a different combination of enhancements.
    """
    base = ImageOps.exif_transpose(pil_image)  # correct camera orientation
    gray = base.convert("L")

    variants = [
        base,  # original (handles already-good images fastest)
        gray,
        ImageEnhance.Contrast(gray).enhance(2.0),
        ImageEnhance.Sharpness(gray).enhance(3.0),
        ImageEnhance.Contrast(ImageEnhance.Sharpness(gray).enhance(2.0)).enhance(2.0),
        gray.filter(ImageFilter.SHARPEN),
    ]
    return variants


def extract_isbn_from_image(image_file) -> str | None:
    """
    Attempt to decode an ISBN barcode from an uploaded image file.

    Args:
        image_file: A file-like object containing an image (JPEG, PNG, WEBP, etc.).

    Returns:
        A validated ISBN-13 string, or None if no barcode was found.

    Raises:
        ImportError: If pyzbar is not installed (system dependency missing).
        ValueError: If the image file cannot be parsed.
    """
    try:
        from pyzbar import pyzbar
    except ImportError:
        raise ImportError(
            "pyzbar is not installed. Install it and ensure libzbar is available on the system."
        )

    try:
        pil_image = Image.open(image_file)
    except Exception as exc:
        raise ValueError(f"Cannot parse image: {exc}") from exc

    seen: set[str] = set()

    for variant in _preprocess_variants(pil_image):
        try:
            decoded_objects = pyzbar.decode(variant)
        except Exception:
            continue

        for obj in decoded_objects:
            raw = obj.data.decode("utf-8", errors="ignore").strip()
            isbn = _normalize_raw(raw)
            if isbn and isbn not in seen:
                seen.add(isbn)
                logger.debug("Barcode detected via pyzbar: %s", isbn)
                return isbn  # first valid ISBN wins

    logger.debug("pyzbar found no valid ISBN barcode in uploaded image")
    return None
