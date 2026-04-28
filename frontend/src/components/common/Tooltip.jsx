import React, { useId } from 'react';
import styles from './Tooltip.module.css';

/**
 * Tooltip — shows a short explanation on hover or keyboard focus.
 *
 * Usage with custom trigger:
 *   <Tooltip content="Your explanation"><span>trigger text</span></Tooltip>
 *
 * Usage as standalone info icon (ⓘ):
 *   <Tooltip content="Your explanation" />
 *
 * @param {object} props
 * @param {string} props.content - Tooltip text to display
 * @param {React.ReactNode} [props.children] - Custom trigger element; defaults to an ⓘ icon button
 * @param {'top'|'bottom'} [props.position='top'] - Preferred position
 */
export default function Tooltip({ content, children, position = 'top' }) {
    const id = useId();

    return (
        <span className={styles.wrapper}>
            {children ? (
                <span className={styles.trigger} aria-describedby={id}>
                    {children}
                </span>
            ) : (
                <button
                    type="button"
                    className={styles.iconButton}
                    aria-describedby={id}
                    aria-label="More information"
                    tabIndex={0}
                >
                    <svg
                        viewBox="0 0 20 20"
                        fill="currentColor"
                        width="14"
                        height="14"
                        aria-hidden="true"
                    >
                        <path
                            fillRule="evenodd"
                            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
                            clipRule="evenodd"
                        />
                    </svg>
                </button>
            )}
            <span
                id={id}
                role="tooltip"
                className={`${styles.bubble} ${position === 'bottom' ? styles.bottom : styles.top}`}
            >
                {content}
            </span>
        </span>
    );
}
