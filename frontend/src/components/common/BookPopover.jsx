import React from 'react';
import * as Popover from '@radix-ui/react-popover';
import { getBookPrimaryAuthor, getBookIsbn } from '../../utils/book.js';
import styles from './BookPopover.module.css';

/**
 * BookPopover — shows detailed book metadata in a popup.
 * @param {object} props
 * @param {object} props.book - The book object containing metadata.
 */
export default function BookPopover({ book }) {
  if (!book) return null;

  const author = getBookPrimaryAuthor(book);
  const isbn = getBookIsbn(book);
  const subjects = Array.isArray(book.subjects) ? book.subjects.slice(0, 5) : [];

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button
          className={styles.trigger}
          aria-label="View book details"
          title="View book details"
          type="button"
          onClick={(e) => e.stopPropagation()}
        >
          <svg
            viewBox="0 0 20 20"
            fill="currentColor"
            width="18"
            height="18"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z"
              clipRule="evenodd"
            />
          </svg>
        </button>
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          className={styles.content}
          sideOffset={5}
          onClick={(e) => e.stopPropagation()}
        >
          <div className={styles.header}>
            <h3 className={styles.title}>{book.title}</h3>
            {author && <p className={styles.author}>by {author}</p>}
          </div>

          <div className={styles.metaRow}>
            {book.physical_format && (
              <>
                <span>{book.physical_format}</span>
                <span className={styles.separator} />
              </>
            )}
            {book.page_count && (
              <>
                <span>{book.page_count} pages</span>
                <span className={styles.separator} />
              </>
            )}
            {book.publish_year && <span>Published {book.publish_year}</span>}
          </div>

          {subjects.length > 0 && (
            <div className={styles.subjects}>
              {subjects.map((subject, index) => (
                <span key={index} className={styles.subjectTag}>
                  {subject}
                </span>
              ))}
            </div>
          )}

          <div className={styles.descriptionWrapper}>
            {book.description ? (
              <p>{book.description}</p>
            ) : (
              <p>No synopsis available for this title.</p>
            )}
          </div>

          <div className={styles.footer}>
            {isbn && <span>ISBN: {isbn}</span>}
            {book.publisher && (
              <div>Publisher: {book.publisher}</div>
            )}
          </div>

          <Popover.Close className={styles.closeButton} aria-label="Close">
            <svg viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
              <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
            </svg>
          </Popover.Close>
          <Popover.Arrow className={styles.arrow} />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
