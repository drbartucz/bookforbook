import React from 'react';
import styles from './Pagination.module.css';

/**
 * Pagination component.
 * @param {object} props
 * @param {number} props.page - Current page (1-based)
 * @param {number} props.totalPages
 * @param {Function} props.onPageChange - Called with new page number
 * @param {boolean} [props.disabled]
 */
export default function Pagination({ page, totalPages, onPageChange, disabled = false }) {
  if (totalPages <= 1) return null;

  const pages = buildPageNumbers(page, totalPages);

  return (
    <nav className={styles.pagination} aria-label="Pagination">
      <button
        className={`${styles.pageBtn} ${styles.navBtn}`}
        onClick={() => onPageChange(page - 1)}
        disabled={disabled || page <= 1}
        aria-label="Previous page"
      >
        <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
          <path fillRule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clipRule="evenodd" />
        </svg>
        Prev
      </button>

      <div className={styles.pageNumbers}>
        {pages.map((p, i) =>
          p === '...' ? (
            <span key={`ellipsis-${i}`} className={styles.ellipsis}>
              &hellip;
            </span>
          ) : (
            <button
              key={p}
              className={`${styles.pageBtn} ${p === page ? styles.active : ''}`}
              onClick={() => onPageChange(p)}
              disabled={disabled || p === page}
              aria-current={p === page ? 'page' : undefined}
            >
              {p}
            </button>
          )
        )}
      </div>

      <button
        className={`${styles.pageBtn} ${styles.navBtn}`}
        onClick={() => onPageChange(page + 1)}
        disabled={disabled || page >= totalPages}
        aria-label="Next page"
      >
        Next
        <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
          <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
        </svg>
      </button>
    </nav>
  );
}

function buildPageNumbers(current, total) {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages = [];

  if (current <= 4) {
    pages.push(1, 2, 3, 4, 5, '...', total);
  } else if (current >= total - 3) {
    pages.push(1, '...', total - 4, total - 3, total - 2, total - 1, total);
  } else {
    pages.push(1, '...', current - 1, current, current + 1, '...', total);
  }

  return pages;
}
