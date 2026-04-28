import React from 'react';
import { Link } from 'react-router-dom';
import ConditionBadge from './ConditionBadge.jsx';
import Tooltip from './Tooltip.jsx';
import { getBookCoverUrl, getBookIsbn, getBookPrimaryAuthor } from '../../utils/book.js';
import styles from './BookCard.module.css';

const PLACEHOLDER_COVER = 'data:image/svg+xml,' + encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" width="120" height="160" viewBox="0 0 120 160">
  <rect width="120" height="160" fill="#e5e7eb"/>
  <rect x="10" y="10" width="100" height="140" rx="4" fill="#f3f4f6"/>
  <rect x="20" y="30" width="80" height="8" rx="2" fill="#d1d5db"/>
  <rect x="20" y="46" width="60" height="6" rx="2" fill="#d1d5db"/>
  <rect x="20" y="80" width="80" height="40" rx="2" fill="#e5e7eb"/>
  <text x="60" y="145" font-family="sans-serif" font-size="10" fill="#9ca3af" text-anchor="middle">No cover</text>
</svg>
`);

/**
 * BookCard — displays a book with cover, title, author, condition badge and optional actions.
 * @param {object} props
 * @param {object} props.book - Book object from the API or legacy UI shape.
 * @param {object} [props.owner] - Owner user object (id, username)
 * @param {Function} [props.onAction] - Primary action callback
 * @param {string} [props.actionLabel] - Label for primary action button
 * @param {boolean} [props.actionLoading] - Loading state for action button
 * @param {React.ReactNode} [props.extra] - Extra content below the card body
 * @param {boolean} [props.compact] - Compact display mode
 */
export default function BookCard({
  book,
  owner,
  copyCount = 1,
  onAction,
  actionLabel,
  actionTooltip,
  actionLoading = false,
  extra,
  compact = false,
}) {
  if (!book) return null;

  const coverUrl = getBookCoverUrl(book) || PLACEHOLDER_COVER;
  const author = getBookPrimaryAuthor(book);
  const isbn = getBookIsbn(book);

  return (
    <div className={`card ${styles.card} ${compact ? styles.compact : ''}`}>
      <div className={styles.coverWrapper}>
        <img
          src={coverUrl}
          alt={book.title ? `Cover of ${book.title}` : 'Book cover'}
          className={styles.cover}
          onError={(e) => {
            e.currentTarget.src = PLACEHOLDER_COVER;
          }}
          loading="lazy"
        />
      </div>
      <div className={styles.body}>
        <div className={styles.info}>
          <h3 className={styles.title} title={book.title}>
            {book.title || 'Unknown title'}
          </h3>
          {author && (
            <p className={styles.author}>{author}</p>
          )}
          {isbn && (
            <p className={styles.isbn}>ISBN: {isbn}</p>
          )}
          <div className={styles.meta}>
            {book.condition && <ConditionBadge condition={book.condition} />}
            {copyCount > 1 && (
              <Tooltip content={`${copyCount} users are currently offering this title. Match availability depends on active listings and wishlist compatibility.`}>
                <span className="badge badge-blue">{copyCount} copies</span>
              </Tooltip>
            )}
            {owner && (
              <Link
                to={`/profile/${owner.id}`}
                className={styles.ownerLink}
                onClick={(e) => e.stopPropagation()}
              >
                @{owner.username}
              </Link>
            )}
          </div>
        </div>
        {onAction && (
          actionTooltip ? (
            <Tooltip content={actionTooltip}>
              <button
                className="btn btn-primary btn-sm"
                onClick={onAction}
                disabled={actionLoading}
              >
                {actionLoading ? 'Loading...' : (actionLabel || 'Action')}
              </button>
            </Tooltip>
          ) : (
            <button
              className="btn btn-primary btn-sm"
              onClick={onAction}
              disabled={actionLoading}
            >
              {actionLoading ? 'Loading...' : (actionLabel || 'Action')}
            </button>
          )
        )}
        {extra && <div className={styles.extra}>{extra}</div>}
      </div>
    </div>
  );
}
