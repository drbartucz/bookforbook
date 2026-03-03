import React from 'react';
import styles from './ErrorMessage.module.css';

/**
 * ErrorMessage component — displays an error with optional retry action.
 * @param {object} props
 * @param {Error|string} props.error
 * @param {Function} [props.onRetry]
 * @param {string} [props.retryLabel]
 */
export default function ErrorMessage({ error, onRetry, retryLabel = 'Try again' }) {
  const message = extractMessage(error);

  return (
    <div className={styles.container} role="alert">
      <div className={styles.icon}>
        <svg viewBox="0 0 20 20" fill="currentColor" width="20" height="20">
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
            clipRule="evenodd"
          />
        </svg>
      </div>
      <div className={styles.content}>
        <p className={styles.message}>{message}</p>
        {onRetry && (
          <button className={styles.retryButton} onClick={onRetry}>
            {retryLabel}
          </button>
        )}
      </div>
    </div>
  );
}

function extractMessage(error) {
  if (!error) return 'An unexpected error occurred.';
  if (typeof error === 'string') return error;

  // Axios error with response data
  const data = error?.response?.data;
  if (data) {
    if (typeof data === 'string') return data;
    if (data.detail) return data.detail;
    if (data.message) return data.message;
    if (data.non_field_errors) return data.non_field_errors.join(' ');
    // flatten first field error
    const firstKey = Object.keys(data)[0];
    if (firstKey) {
      const val = data[firstKey];
      return Array.isArray(val) ? `${firstKey}: ${val.join(' ')}` : `${firstKey}: ${val}`;
    }
  }

  return error.message || 'An unexpected error occurred.';
}
