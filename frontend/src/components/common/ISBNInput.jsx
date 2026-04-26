import React, { useState } from 'react';
import { books as booksApi } from '../../services/api.js';
import {
  getBookCoverUrl,
  getBookPrimaryAuthor,
  getBookPublishYear,
} from '../../utils/book.js';
import styles from './ISBNInput.module.css';

/**
 * ISBNInput — ISBN input with lookup button and book preview.
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
  const [lookupError, setLookupError] = useState(null);
  const [localBook, setLocalBook] = useState(null);
  const [hasBlurred, setHasBlurred] = useState(false);
  const [hasLookupAttempted, setHasLookupAttempted] = useState(false);

  const displayBook = foundBook ?? localBook;
  const previewAuthor = getBookPrimaryAuthor(displayBook);
  const previewYear = getBookPublishYear(displayBook);
  const previewCover = getBookCoverUrl(displayBook);

  async function handleLookup() {
    setHasLookupAttempted(true);
    const isbn = value.trim().replace(/[\s-]/g, '');
    if (!isbn) return;

    if (isbn.length !== 10 && isbn.length !== 13) {
      setLookupError('ISBN must be 10 or 13 digits.');
      return;
    }

    setLooking(true);
    setLookupError(null);

    try {
      const res = await booksApi.lookupISBN(isbn);
      const bookData = res.data;
      setLocalBook(bookData);
      if (onBookFound) {
        onBookFound(bookData);
      }
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        'Book not found for this ISBN.';
      setLookupError(msg);
      setLocalBook(null);
      if (onBookFound) {
        onBookFound(null);
      }
    } finally {
      setLooking(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleLookup();
    }
  }

  function handleChange(e) {
    onChange(e.target.value.trim());
    // Clear lookup result when user types a new ISBN
    if (localBook) {
      setLocalBook(null);
      if (onBookFound) onBookFound(null);
    }
    setLookupError(null);
  }

  const shouldShowError = hasBlurred || hasLookupAttempted;
  const visibleError = shouldShowError ? (error || lookupError) : null;

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
          disabled={disabled || looking}
          inputMode="numeric"
          maxLength={20}
          aria-label="ISBN"
        />
        <button
          type="button"
          className={`btn btn-secondary ${styles.lookupBtn}`}
          onClick={handleLookup}
          disabled={disabled || looking || !value.trim()}
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
