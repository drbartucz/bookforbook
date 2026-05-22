import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { myBooks as myBooksApi, donations as donationsApi } from '../../services/api.js';
import LoadingSpinner from './LoadingSpinner.jsx';
import ConditionBadge from './ConditionBadge.jsx';

const CONDITION_RANK = { like_new: 4, very_good: 3, good: 2, acceptable: 1 };

function conditionMeetsMin(condition, minCondition) {
  return (CONDITION_RANK[condition] ?? 0) >= (CONDITION_RANK[minCondition] ?? 0);
}

/**
 * Two modes:
 *
 * "Choose recipient" — triggered from My Books.
 *   Required props: userBook (the UserBook being gifted)
 *   Fetches /my-books/:id/wanted-by/ and shows a list of potential recipients.
 *
 * "Confirm gift" — triggered from a profile's wishlist.
 *   Required props: recipientId, recipientUsername, userBookId, book
 *   Shows a simple confirmation before submitting.
 */
export default function GiftModal({ open, onClose, onSuccess, userBook, recipientId, recipientUsername, userBookId, book }) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState('');
  const [error, setError] = useState(null);

  const isChooseRecipientMode = !!userBook && !recipientId;
  const isConfirmMode = !!recipientId && !!userBookId;

  const { data: wantedBy, isLoading: wantedByLoading } = useQuery({
    queryKey: ['wantedBy', userBook?.id],
    queryFn: () => myBooksApi.wantedBy(userBook.id).then((r) => r.data),
    enabled: open && isChooseRecipientMode,
  });

  const offerMutation = useMutation({
    mutationFn: ({ recipientId: rid, ubId }) =>
      donationsApi.offer({ recipient_id: rid, user_book_id: ubId, message }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myBooks'] });
      queryClient.invalidateQueries({ queryKey: ['donations'] });
      setError(null);
      setMessage('');
      onSuccess?.();
      onClose();
    },
    onError: (err) => {
      const data = err?.response?.data;
      const msg =
        data?.non_field_errors?.[0] ||
        data?.recipient_id?.[0] ||
        data?.user_book_id?.[0] ||
        data?.detail ||
        'Failed to send gift offer.';
      setError(msg);
    },
  });

  if (!open) return null;

  const displayBook = userBook?.book ?? book;

  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) onClose();
  }

  function handleConfirm(rid, ubId) {
    setError(null);
    offerMutation.mutate({ recipientId: rid, ubId });
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(17,24,39,0.5)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 60, padding: '1rem',
      }}
      onMouseDown={handleBackdropClick}
    >
      <div className="card" style={{ width: 'min(520px, 100%)', padding: '1.5rem' }} role="dialog" aria-modal="true">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
          <h3 style={{ margin: 0 }}>Gift a Book</h3>
          <button
            className="btn btn-secondary btn-sm"
            onClick={onClose}
            style={{ padding: '0.25rem 0.5rem' }}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {displayBook && (
          <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', padding: '0.75rem', background: 'var(--color-bg-subtle, #f9fafb)', borderRadius: '0.5rem' }}>
            {displayBook.cover_image_url && (
              <img src={displayBook.cover_image_url} alt={displayBook.title} style={{ width: 48, height: 68, objectFit: 'cover', flexShrink: 0 }} />
            )}
            <div>
              <p style={{ margin: '0 0 0.25rem', fontWeight: 600 }}>{displayBook.title}</p>
              {displayBook.authors && (
                <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--color-text-muted, #6b7280)' }}>
                  {Array.isArray(displayBook.authors) ? displayBook.authors[0] : displayBook.authors}
                </p>
              )}
              {userBook?.condition && <ConditionBadge condition={userBook.condition} />}
            </div>
          </div>
        )}

        {error && <div className="alert alert-error" style={{ marginBottom: '1rem' }}>{error}</div>}

        {isChooseRecipientMode && (
          <>
            <p style={{ margin: '0 0 0.75rem', fontSize: '0.875rem', color: 'var(--color-text-muted, #6b7280)' }}>
              Choose who to gift this book to. They won't owe you anything in return.
            </p>

            {wantedByLoading ? (
              <LoadingSpinner center />
            ) : !wantedBy?.length ? (
              <p style={{ textAlign: 'center', color: 'var(--color-text-muted, #6b7280)', padding: '1rem 0' }}>
                No one has this book on their wishlist right now.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '280px', overflowY: 'auto' }}>
                {wantedBy.map((entry) => {
                  const eligible = conditionMeetsMin(userBook.condition, entry.min_condition);
                  return (
                    <div
                      key={entry.wishlist_item_id}
                      style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: '0.625rem 0.75rem', border: '1px solid var(--color-border, #e5e7eb)',
                        borderRadius: '0.5rem',
                        opacity: eligible ? 1 : 0.5,
                      }}
                    >
                      <div>
                        <span style={{ fontWeight: 500 }}>@{entry.user.username}</span>
                        {entry.user.account_type !== 'individual' && (
                          <span className="badge badge-blue" style={{ marginLeft: '0.5rem' }}>Institution</span>
                        )}
                        <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted, #6b7280)', marginTop: '0.125rem' }}>
                          Wants min: <ConditionBadge condition={entry.min_condition} />
                        </div>
                      </div>
                      <button
                        className="btn btn-primary btn-sm"
                        disabled={!eligible || offerMutation.isPending}
                        onClick={() => handleConfirm(entry.user.id, userBook.id)}
                        title={eligible ? undefined : `Your copy doesn't meet their minimum condition (${entry.min_condition})`}
                      >
                        Gift
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="form-group" style={{ marginTop: '1rem' }}>
              <label className="form-label" htmlFor="giftMessage">Message (optional)</label>
              <textarea
                id="giftMessage"
                className="form-input"
                rows={2}
                maxLength={1000}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Add a personal note..."
                style={{ resize: 'vertical' }}
              />
            </div>
          </>
        )}

        {isConfirmMode && (
          <>
            <p style={{ margin: '0 0 1rem', fontSize: '0.9375rem' }}>
              Gift this book to <strong>@{recipientUsername}</strong>? They won't owe you anything in return.
            </p>

            <div className="form-group">
              <label className="form-label" htmlFor="giftMessageConfirm">Message (optional)</label>
              <textarea
                id="giftMessageConfirm"
                className="form-input"
                rows={2}
                maxLength={1000}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Add a personal note..."
                style={{ resize: 'vertical' }}
              />
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '0.75rem' }}>
              <button className="btn btn-secondary" onClick={onClose} disabled={offerMutation.isPending}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={() => handleConfirm(recipientId, userBookId)}
                disabled={offerMutation.isPending}
              >
                {offerMutation.isPending ? 'Sending...' : 'Send gift offer'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
