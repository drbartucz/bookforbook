import React from 'react';
import styles from './LoadingSpinner.module.css';

/**
 * LoadingSpinner component.
 * @param {object} props
 * @param {'sm'|'md'|'lg'} props.size
 * @param {string} props.label - Accessible label (default "Loading...")
 * @param {boolean} props.center - Center within parent
 */
export default function LoadingSpinner({ size = 'md', label = 'Loading...', center = false }) {
  return (
    <div
      className={`${styles.wrapper} ${center ? styles.center : ''}`}
      role="status"
      aria-label={label}
    >
      <div className={`${styles.spinner} ${styles[size]}`} />
      <span className="sr-only">{label}</span>
    </div>
  );
}
