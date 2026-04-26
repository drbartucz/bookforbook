import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { donations as donationsApi } from '../services/api.js';
import LoadingSpinner from '../components/common/LoadingSpinner.jsx';
import ErrorMessage from '../components/common/ErrorMessage.jsx';
import ConditionBadge from '../components/common/ConditionBadge.jsx';
import Pagination from '../components/common/Pagination.jsx';
import { format } from 'date-fns';
import { getBookCoverUrl, getBookPrimaryAuthor } from '../utils/book.js';
import styles from './Donations.module.css';

const PAGE_SIZE = 15;

const STATUS_CONFIG = {
  offered: { label: 'Offered', cls: 'badge-amber' },
  accepted: { label: 'Accepted', cls: 'badge-green' },
  shipped: { label: 'Shipped', cls: 'badge-blue' },
  received: { label: 'Received', cls: 'badge-green' },
  cancelled: { label: 'Declined', cls: 'badge-red' },
};

const DIRECTION_TABS = [
  { value: '', label: 'All' },
  { value: 'offered', label: 'Offered by me' },
  { value: 'received', label: 'Received' },
];

export default function Donations() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [direction, setDirection] = useState('');
  const [actionError, setActionError] = useState(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['donations', direction, page],
    queryFn: () => {
      const params = { page, page_size: PAGE_SIZE };
      if (direction) params.direction = direction;
      return donationsApi.list(params).then((r) => r.data);
    },
  });

  const acceptMutation = useMutation({
    mutationFn: (id) => donationsApi.accept(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['donations'] });
      setActionError(null);
    },
    onError: (err) => setActionError(err?.response?.data?.detail || 'Failed to accept.'),
  });

  const declineMutation = useMutation({
    mutationFn: (id) => donationsApi.decline(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['donations'] });
      setActionError(null);
    },
    onError: (err) => setActionError(err?.response?.data?.detail || 'Failed to decline.'),
  });

  const items = Array.isArray(data) ? data : (data?.results ?? []);
  const totalPages = Math.ceil((Array.isArray(data) ? data.length : (data?.count ?? 0)) / PAGE_SIZE);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Donations</h1>
        <p className="page-subtitle">
          Institutions (libraries, bookstores) can receive book donations from individuals.
        </p>
      </div>

      <div className={styles.tabs}>
        {DIRECTION_TABS.map((tab) => (
          <button
            key={tab.value}
            className={`${styles.tab} ${direction === tab.value ? styles.activeTab : ''}`}
            onClick={() => { setDirection(tab.value); setPage(1); }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {actionError && (
        <div className="alert alert-error" style={{ marginBottom: '1rem' }}>
          {actionError}
        </div>
      )}

      {isLoading ? (
        <LoadingSpinner center size="lg" />
      ) : isError ? (
        <ErrorMessage error={error} onRetry={refetch} />
      ) : items.length === 0 ? (
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>No donations found</p>
          <p className={styles.emptySubtitle}>
            Browse institution profiles to see their wanted book lists and offer donations.
          </p>
        </div>
      ) : (
        <>
          <div className={styles.donationList}>
            {items.map((donation) => {
              const statusConfig = STATUS_CONFIG[donation.status] ?? { label: donation.status, cls: 'badge-gray' };
              const userBook = donation.user_book ?? donation.book;
              const book = userBook?.book ?? userBook;
              const donor = donation.donor ?? donation.from_user;
              const recipient = donation.institution ?? donation.recipient ?? donation.to_user;
              const isPending = donation.status === 'offered';
              const isRecipient = donation.is_recipient ?? false;

              return (
                <div key={donation.id} className={`card ${styles.donationCard}`}>
                  <div className={styles.donationHeader}>
                    <span className={`badge ${statusConfig.cls}`}>{statusConfig.label}</span>
                    {donation.created_at && (
                      <span className={styles.donationDate}>
                        {format(new Date(donation.created_at), 'MMM d, yyyy')}
                      </span>
                    )}
                  </div>

                  <div className={styles.donationBody}>
                    {book ? (
                      <div className={styles.bookInfo}>
                        {getBookCoverUrl(book) && (
                          <img src={getBookCoverUrl(book)} alt={book.title} className={styles.bookCover} />
                        )}
                        <div>
                          <p className={styles.bookTitle}>{book.title}</p>
                          {getBookPrimaryAuthor(book) && <p className={styles.bookAuthor}>{getBookPrimaryAuthor(book)}</p>}
                          {(book.isbn_13 || book.isbn_10) && (
                            <p className={styles.bookIsbn}>ISBN: {book.isbn_13 || book.isbn_10}</p>
                          )}
                          {userBook?.condition && (
                            <ConditionBadge condition={userBook.condition} />
                          )}
                        </div>
                      </div>
                    ) : (
                      <p className={styles.noBook}>Book info unavailable</p>
                    )}

                    <div className={styles.participants}>
                      {donor && (
                        <div className={styles.participant}>
                          <span className={styles.participantLabel}>From</span>
                          <a href={`/profile/${donor.id}`} className={styles.participantName}>
                            @{donor.username}
                          </a>
                        </div>
                      )}
                      {recipient && (
                        <div className={styles.participant}>
                          <span className={styles.participantLabel}>To</span>
                          <a href={`/profile/${recipient.id}`} className={styles.participantName}>
                            @{recipient.username ?? recipient.name}
                          </a>
                        </div>
                      )}
                    </div>
                  </div>

                  {isPending && isRecipient && (
                    <div className={styles.donationActions}>
                      <button
                        className="btn btn-success btn-sm"
                        onClick={() => acceptMutation.mutate(donation.id)}
                        disabled={acceptMutation.isPending}
                      >
                        Accept Donation
                      </button>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => declineMutation.mutate(donation.id)}
                        disabled={declineMutation.isPending}
                      >
                        Decline
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
