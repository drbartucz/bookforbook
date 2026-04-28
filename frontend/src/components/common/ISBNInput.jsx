import React, { useRef, useState } from 'react';
import { books as booksApi } from '../../services/api.js';
import {
  getBookCoverUrl,
  getBookPrimaryAuthor,
  getBookPublishYear,
} from '../../utils/book.js';
import { detectISBNFromFile } from '../../utils/isbnDetect.js';
import styles from './ISBNInput.module.css';

/**
 * ISBNInput — ISBN text input with optional image-based barcode scan.
 *
 * Detection pipeline (triggered by image upload):
 *  1. Client-side BarcodeDetector (native API or WASM polyfill)
 *  2. Tesseract.js digit-only OCR on bottom crop
 *  3. Backend /books/from-image/ as final server-side fallback
 *
 * @param {object} props
 * @param {string} props.value - Current ISBN value
 * @param {Function} props.onChange - Called with new ISBN string
 * @param {Function} props.onBookFound - Called with book data object when lookup succeeds
 * @param {object} [props.foundBook] - Currently found book (controlled)
 * @param {string} [props.error] - Validation error message
 * @param {boolean} [props.disabled]
 */
export default function ISBNInput({
  value,
  onChange,
  onBookFound,
  foundBook,
  error,
  disabled = false,
}) {
  const [looking, setLooking] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [scanPhase, setScanPhase] = useState(null); // 'barcode' | 'ocr' | 'server'
  const [lookupError, setLookupError] = useState(null);
  const [localBook, setLocalBook] = useState(null);
  const [hasBlurred, setHasBlurred] = useState(false);
  const [hasLookupAttempted, setHasLookupAttempted] = useState(false);
  // Multiple ISBN candidates from OCR (rare edge case)
  const [isbnCandidates, setIsbnCandidates] = useState(null);

  const fileInputRef = useRef(null);

  const displayBook = foundBook ?? localBook;
  const previewAuthor = getBookPrimaryAuthor(displayBook);
  const previewYear = getBookPublishYear(displayBook);
  const previewCover = getBookCoverUrl(displayBook);

  // ── ISBN text lookup ────────────────────────────────────────────────────────

  async function performLookup(isbn) {
    setLooking(true);
    setLookupError(null);
    try {
      const res = await booksApi.lookupISBN(isbn);
      const bookData = res.data;
      setLocalBook(bookData);
      if (onBookFound) onBookFound(bookData);
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        'Book not found for this ISBN.';
      setLookupError(msg);
      setLocalBook(null);
      if (onBookFound) onBookFound(null);
    } finally {
      setLooking(false);
    }
  }

  async function handleLookup() {
    setHasLookupAttempted(true);
    const isbn = value.trim().replace(/[\s-]/g, '');
    if (!isbn) return;
    if (isbn.length !== 10 && isbn.length !== 13) {
      setLookupError('ISBN must be 10 or 13 digits.');
      return;
    }
    await performLookup(isbn);
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleLookup();
    }
  }

  function handleChange(e) {
    onChange(e.target.value.trim());
    if (localBook) {
      setLocalBook(null);
      if (onBookFound) onBookFound(null);
    }
    setIsbnCandidates(null);
    setLookupError(null);
  }

  // ── Image scan ──────────────────────────────────────────────────────────────

  function handleScanClick() {
    if (fileInputRef.current) fileInputRef.current.click();
  }

  async function handleFileChange(e) {
    const file = e.target.files?.[0];
    // Reset so the same file can be re-selected after a failure
    e.target.value = '';
    if (!file) return;

    setScanning(true);
    setLookupError(null);
    setIsbnCandidates(null);
    setLocalBook(null);
    if (onBookFound) onBookFound(null);

    try {
      // Tier 1 + 2: client-side barcode detection then OCR
      setScanPhase('barcode');
      const result = await detectISBNFromFile(file);

      if (result.status === 'found') {
        onChange(result.isbn);
        setScanning(false);
        setScanPhase(null);
        await performLookup(result.isbn);
        return;
      }

      if (result.status === 'multiple') {
        // Surface candidates for user selection; don't auto-pick
        setIsbnCandidates(result.candidates);
        setScanning(false);
        setScanPhase(null);
        return;
      }

      // Tier 3: backend fallback (runs pyzbar with PIL preprocessing)
      setScanPhase('server');
      try {
        const res = await booksApi.fromImage(file);
        const isbn = res.data?.isbn;
        if (isbn) {
          onChange(isbn);
          setScanning(false);
          setScanPhase(null);
          await performLookup(isbn);
          return;
        }
      } catch (backendErr) {
        if (backendErr?.response?.status !== 404) {
          // 404 = no barcode found, other errors are unexpected
          setLookupError('Server error during scan. Please try again or enter ISBN manually.');
          setScanning(false);
          setScanPhase(null);
          return;
        }
      }

      // All tiers exhausted
      setLookupError('No ISBN found in image. Try a clearer photo or enter it manually.');
    } catch {
      setLookupError('Could not read image. Please try again or enter the ISBN manually.');
    } finally {
      setScanning(false);
      setScanPhase(null);
    }
  }

  function handleCandidateSelect(isbn) {
    setIsbnCandidates(null);
    onChange(isbn);
    performLookup(isbn);
  }

  // ── Render helpers ──────────────────────────────────────────────────────────

  const isWorking = looking || scanning;
  const shouldShowError = hasBlurred || hasLookupAttempted;
  const visibleError = shouldShowError ? (error || lookupError) : lookupError;

  function scanLabel() {
    if (!scanning) return null;
    if (scanPhase === 'server') return 'Checking server…';
    if (scanPhase === 'ocr') return 'Reading text…';
    return 'Scanning…';
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.inputRow}>
        <input
          type="text"
          className={`form-input ${visibleError ? 'error' : ''} ${styles.input}`}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onBlur={() => setHasBlurred(true)}
          placeholder="e.g. 9780141439518"
          disabled={isWorking || disabled}
          inputMode="numeric"
          maxLength={20}
          aria-label="ISBN"
        />

        {/* Image scan button */}
        <button
          type="button"
          className={`btn btn-secondary ${styles.scanBtn}`}
          onClick={handleScanClick}
          disabled={isWorking || disabled}
          aria-label="Scan barcode or ISBN from image"
          title="Upload a photo of the book's barcode or ISBN"
        >
          {scanning ? (
            <span className={styles.spinner} aria-hidden="true" />
          ) : (
            <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16" aria-hidden="true">
              <path d="M2 3.5A1.5 1.5 0 013.5 2h1A1.5 1.5 0 016 3.5v1A1.5 1.5 0 014.5 6h-1A1.5 1.5 0 012 4.5v-1zM2 10a.75.75 0 01.75-.75h.5a.75.75 0 010 1.5h-.5A.75.75 0 012 10zm0 3.5a.75.75 0 01.75-.75h.5a.75.75 0 010 1.5h-.5a.75.75 0 01-.75-.75zm3-3.5a.75.75 0 01.75-.75h.5a.75.75 0 010 1.5h-.5A.75.75 0 015 10zm0 3.5a.75.75 0 01.75-.75h.5a.75.75 0 010 1.5h-.5a.75.75 0 01-.75-.75zM8 3.5A1.5 1.5 0 019.5 2h1A1.5 1.5 0 0112 3.5v1A1.5 1.5 0 0110.5 6h-1A1.5 1.5 0 018 4.5v-1zM8 10a.75.75 0 01.75-.75h.5a.75.75 0 010 1.5h-.5A.75.75 0 018 10zm0 3.5a.75.75 0 01.75-.75h.5a.75.75 0 010 1.5h-.5a.75.75 0 01-.75-.75zM14 3.5A1.5 1.5 0 0115.5 2h1A1.5 1.5 0 0118 3.5v1A1.5 1.5 0 0116.5 6h-1A1.5 1.5 0 0114 4.5v-1zM14 10a.75.75 0 01.75-.75h.5a.75.75 0 010 1.5h-.5a.75.75 0 01-.75-.75zm0 3.5a.75.75 0 01.75-.75h.5a.75.75 0 010 1.5h-.5a.75.75 0 01-.75-.75z" />
            </svg>
          )}
          {scanning ? scanLabel() : 'Scan'}
        </button>

        {/* Hidden file input — image only */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className={styles.hiddenFileInput}
          onChange={handleFileChange}
          aria-hidden="true"
          tabIndex={-1}
        />

        {/* Text lookup button */}
        <button
          type="button"
          className={`btn btn-secondary ${styles.lookupBtn}`}
          onClick={handleLookup}
          disabled={isWorking || disabled || !value.trim()}
        >
          {looking ? (
            <span className={styles.spinner} />
          ) : (
            <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
              <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clipRule="evenodd" />
            </svg>
          )}
          Lookup
        </button>
      </div>

      {visibleError && (
        <p className="form-error">{visibleError}</p>
      )}

      {/* Multiple OCR candidates — rare edge case */}
      {isbnCandidates && (
        <div className={styles.candidateList}>
          <p className={styles.candidateHint}>Multiple ISBNs found — pick one:</p>
          {isbnCandidates.map((isbn) => (
            <button
              key={isbn}
              type="button"
              className={`btn btn-secondary ${styles.candidateBtn}`}
              onClick={() => handleCandidateSelect(isbn)}
            >
              {isbn}
            </button>
          ))}
        </div>
      )}

      {displayBook && (
        <div className={styles.bookPreview}>
          {previewCover && (
            <img
              src={previewCover}
              alt="Book cover"
              className={styles.previewCover}
            />
          )}
          <div className={styles.previewInfo}>
            <p className={styles.previewTitle}>{displayBook.title}</p>
            {previewAuthor && (
              <p className={styles.previewAuthor}>{previewAuthor}</p>
            )}
            {previewYear && (
              <p className={styles.previewMeta}>{previewYear}</p>
            )}
          </div>
          <span className="badge badge-green" style={{ alignSelf: 'flex-start', flexShrink: 0 }}>
            Found
          </span>
        </div>
      )}
    </div>
  );
}
