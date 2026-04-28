/**
 * ISBN detection from uploaded images.
 *
 * Detection pipeline (in priority order):
 *  1. BarcodeDetector API (native or WASM polyfill) — deterministic, checksum-safe
 *  2. Tesseract.js OCR on bottom crop, digits-only — targeted text fallback
 *  3. Backend upload — caller handles this tier if needed
 *
 * Barcode always wins over OCR when both produce a valid ISBN.
 */

// ── ISBN math helpers (mirrors backend normalize_isbn logic) ──────────────────

function _isbn13CheckDigit(first12) {
  let total = 0;
  for (let i = 0; i < 12; i++) {
    total += parseInt(first12[i]) * (i % 2 === 0 ? 1 : 3);
  }
  return (10 - (total % 10)) % 10;
}

export function validateISBN13(digits) {
  if (!/^\d{13}$/.test(digits)) return false;
  return _isbn13CheckDigit(digits.slice(0, 12)) === parseInt(digits[12]);
}

export function validateISBN10(digits) {
  if (!/^\d{9}[\dX]$/i.test(digits)) return false;
  let total = 0;
  for (let i = 0; i < 10; i++) {
    const c = digits[i].toUpperCase();
    total += (10 - i) * (c === 'X' ? 10 : parseInt(c));
  }
  return total % 11 === 0;
}

export function isbn10ToISBN13(isbn10) {
  const cleaned = isbn10.replace(/[\s\-]/g, '');
  if (cleaned.length !== 10 || !validateISBN10(cleaned)) return null;
  const base = '978' + cleaned.slice(0, 9);
  return base + _isbn13CheckDigit(base);
}

/**
 * Normalize a raw string to canonical ISBN-13.
 * Accepts ISBN-10 or ISBN-13 with optional dashes/spaces.
 * Returns null if invalid.
 */
export function normalizeToISBN13(raw) {
  if (!raw) return null;
  const digits = raw.replace(/[\s\-]/g, '');
  if (digits.length === 13 && validateISBN13(digits)) return digits;
  if (digits.length === 10) return isbn10ToISBN13(digits);
  return null;
}

/**
 * Extract ISBN candidates from OCR text.
 * Prefers ISBN-13 (978/979 prefix); also converts valid ISBN-10 sequences.
 * Returns an array of canonical ISBN-13 strings, deduplicated.
 */
export function extractISBNCandidates(text) {
  const candidates = new Set();

  // ISBN-13: 13 consecutive digits starting with 978 or 979
  const matches13 = text.match(/97[89]\d{10}/g) || [];
  for (const m of matches13) {
    if (validateISBN13(m)) candidates.add(m);
  }

  // ISBN-10: 9 digits + digit or X, not already captured as part of ISBN-13
  // Use word-boundary-style approach to avoid picking up slices of ISBN-13
  const sanitized = text.replace(/97[89]\d{10}/g, ''); // remove ISBN-13 matches first
  const matches10 = sanitized.match(/\d{9}[\dX]/gi) || [];
  for (const m of matches10) {
    const isbn13 = isbn10ToISBN13(m.toUpperCase());
    if (isbn13) candidates.add(isbn13);
  }

  return [...candidates];
}

// ── Step 1: Barcode detection ─────────────────────────────────────────────────

const BARCODE_FORMATS = ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'qr_code'];

/**
 * Try to detect an ISBN barcode in imageElement.
 * Uses native BarcodeDetector if available, otherwise the WASM polyfill.
 * Returns a valid ISBN-13 string, or null if none found.
 */
export async function detectBarcodeISBN(imageElement) {
  let detector;
  try {
    if ('BarcodeDetector' in window) {
      detector = new window.BarcodeDetector({ formats: BARCODE_FORMATS });
    } else {
      // Lazy-load polyfill — only fetches WASM when native API is absent
      const { BarcodeDetector: Polyfill } = await import('barcode-detector/pure');
      detector = new Polyfill({ formats: BARCODE_FORMATS });
    }
  } catch {
    return null;
  }

  try {
    const barcodes = await detector.detect(imageElement);
    for (const barcode of barcodes) {
      const isbn = normalizeToISBN13(barcode.rawValue);
      if (isbn) return isbn;
    }
    return null;
  } catch {
    return null;
  }
}

// ── Step 2: OCR fallback ──────────────────────────────────────────────────────

/**
 * Build a preprocessed canvas cropped to the bottom portion of an image
 * (where ISBNs are printed on back covers).
 * Applies grayscale + contrast enhancement for better OCR accuracy.
 */
function buildCroppedCanvas(imageElement) {
  const fullWidth = imageElement.naturalWidth || imageElement.width;
  const fullHeight = imageElement.naturalHeight || imageElement.height;

  // Crop to bottom 45% of image where ISBN text typically lives
  const cropY = Math.floor(fullHeight * 0.55);
  const cropHeight = fullHeight - cropY;

  const canvas = document.createElement('canvas');
  canvas.width = fullWidth;
  canvas.height = cropHeight;

  const ctx = canvas.getContext('2d');
  // Grayscale + contrast boost before OCR
  ctx.filter = 'grayscale(1) contrast(1.6)';
  ctx.drawImage(imageElement, 0, cropY, fullWidth, cropHeight, 0, 0, fullWidth, cropHeight);

  return canvas;
}

/**
 * Run digit-only OCR on the bottom crop of imageElement.
 * Returns an array of valid ISBN-13 strings, or null if none found.
 * Tesseract.js is lazy-loaded to avoid impacting initial bundle size.
 */
export async function detectOCRISBN(imageElement) {
  let createWorker;
  try {
    ({ createWorker } = await import('tesseract.js'));
  } catch {
    return null;
  }

  const canvas = buildCroppedCanvas(imageElement);

  const worker = await createWorker('eng', 1, {
    logger: () => {}, // suppress progress logs
  });

  try {
    // Restrict recognition to digits + X only (ISBN-10 check characters)
    await worker.setParameters({ tessedit_char_whitelist: '0123456789X' });
    const { data: { text } } = await worker.recognize(canvas);
    const candidates = extractISBNCandidates(text);
    return candidates.length > 0 ? candidates : null;
  } finally {
    await worker.terminate();
  }
}

// ── Public entry point ────────────────────────────────────────────────────────

/**
 * Detect ISBN from an image File object.
 *
 * Returns one of:
 *  { status: 'found',    isbn: string,          method: 'barcode'|'ocr' }
 *  { status: 'multiple', candidates: string[],  method: 'ocr' }
 *  { status: 'failed' }
 *
 * Does NOT call the backend — callers are responsible for the backend fallback tier.
 */
export async function detectISBNFromFile(file) {
  let objectUrl = null;

  try {
    objectUrl = URL.createObjectURL(file);

    const img = await new Promise((resolve, reject) => {
      const el = new Image();
      el.onload = () => resolve(el);
      el.onerror = () => reject(new Error('Could not load image'));
      el.src = objectUrl;
    });

    // --- Tier 1: Barcode (authoritative) ---
    const barcodeISBN = await detectBarcodeISBN(img);
    if (barcodeISBN) {
      return { status: 'found', isbn: barcodeISBN, method: 'barcode' };
    }

    // --- Tier 2: OCR on bottom crop (targeted fallback) ---
    const ocrCandidates = await detectOCRISBN(img);
    if (ocrCandidates) {
      if (ocrCandidates.length === 1) {
        return { status: 'found', isbn: ocrCandidates[0], method: 'ocr' };
      }
      return { status: 'multiple', candidates: ocrCandidates, method: 'ocr' };
    }

    return { status: 'failed' };
  } catch {
    return { status: 'failed' };
  } finally {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
  }
}
