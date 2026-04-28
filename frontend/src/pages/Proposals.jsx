import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { proposals as proposalsApi } from '../services/api.js';
import LoadingSpinner from '../components/common/LoadingSpinner.jsx';
import ErrorMessage from '../components/common/ErrorMessage.jsx';
import ConditionBadge from '../components/common/ConditionBadge.jsx';
import Pagination from '../components/common/Pagination.jsx';
import { getBookCoverUrl, getBookPrimaryAuthor } from '../utils/book.js';
import useAuth from '../hooks/useAuth.js';
import { mapProposalForCard } from '../adapters/proposals.js';
import Tooltip from '../components/common/Tooltip.jsx';
import styles from './Proposals.module.css';

const PAGE_SIZE = 15;

const STATUS_TABS = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'declined', label: 'Declined' },
];

const DIRECTION_TABS = [
  { value: '', label: 'All' },
  { value: 'received', label: 'Received' },
  { value: 'sent', label: 'Sent' },
];

const STATUS_CONFIG = {
  pending: { label: 'Pending', cls: 'badge-amber' },
  accepted: { label: 'Accepted', cls: 'badge-green' },
  declined: { label: 'Declined', cls: 'badge-red' },
  expired: { label: 'Expired', cls: 'badge-gray' },
};

export default function Proposals() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [direction, setDirection] = useState('received');
  const [actionError, setActionError] = useState(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['proposals', statusFilter, direction, page],
    queryFn: () => {
      const params = { page, page_size: PAGE_SIZE };
      if (statusFilter) params.status = statusFilter;
      if (direction) params.direction = direction;
      return proposalsApi.list(params).then((r) => r.data);
    },
  });

  const acceptMutation = useMutation({
    mutationFn: (id) => proposalsApi.accept(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      setActionError(null);
    },
    onError: (err) => setActionError(err?.response?.data?.detail || 'Failed to accept.'),
  });

  const declineMutation = useMutation({
    mutationFn: (id) => proposalsApi.decline(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
      setActionError(null);
    },
    onError: (err) => setActionError(err?.response?.data?.detail || 'Failed to decline.'),
  });

  const rawItems = Array.isArray(data) ? data : (data?.results ?? []);
  const items = rawItems.map((proposal) => mapProposalForCard(proposal, user?.id));
  const totalPages = Math.ceil((Array.isArray(data) ? data.length : (data?.count ?? 0)) / PAGE_SIZE);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Proposals</h1>
        <p className="page-subtitle">Direct trade proposals between you and other users.</p>
      </div>

      {/* Direction tabs */}
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

      {/* Status filter */}
      <div className={styles.statusRow}>
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            className={`btn btn-sm ${statusFilter === tab.value ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => { setStatusFilter(tab.value); setPage(1); }}
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
          <p className={styles.emptyTitle}>No proposals found</p>
          <p className={styles.emptySubtitle}>
            When another user sends you a direct trade proposal, it will appear here.
          </p>
        </div>
      ) : (
        <>
          <div className={styles.proposalList}>
            {items.map((proposal) => {
              const statusConfig = STATUS_CONFIG[proposal.status] ?? { label: proposal.status, cls: 'badge-gray' };
              const offeredBook = proposal.offeredBook;
              const requestedBook = proposal.requestedBook;
              const proposer = proposal.proposer ?? proposal.sender;
              const receiver = proposal.receiver ?? proposal.recipient;
              const canAct = proposal.status === 'pending' && (direction === 'received' || !direction);

              return (
                <div key={proposal.id} className={`card ${styles.proposalCard}`}>
                  <div className={styles.proposalHeader}>
                    <div className={styles.proposalMeta}>
                      <span className={`badge ${statusConfig.cls}`}>{statusConfig.label}</span>
                      <span className={styles.proposalId}>#{proposal.id}</span>
                    </div>
                    <div className={styles.userInfo}>
                      {proposer && (
                        <span className={styles.userLabel}>
                          From: <a href={`/profile/${proposer.id}`}>@{proposer.username}</a>
                        </span>
                      )}
                      {receiver && (
                        <span className={styles.userLabel}>
                          To: <a href={`/profile/${receiver.id}`}>@{receiver.username}</a>
                        </span>
                      )}
                    </div>
                  </div>

                  <div className={styles.booksRow}>
                    <div className={styles.bookCol}>
                      <p className={styles.bookLabel}>Offered</p>
                      {offeredBook && (
                        <div className={styles.bookInfo}>
                          {getBookCoverUrl(offeredBook) && (
                            <img src={getBookCoverUrl(offeredBook)} alt={offeredBook.title} className={styles.bookCover} />
                          )}
                          <div>
                            <p className={styles.bookTitle}>{offeredBook.title}</p>
                            {getBookPrimaryAuthor(offeredBook) && <p className={styles.bookAuthor}>{getBookPrimaryAuthor(offeredBook)}</p>}
                            {(offeredBook.isbn_13 || offeredBook.isbn_10) && (
                              <p className={styles.bookIsbn}>ISBN: {offeredBook.isbn_13 || offeredBook.isbn_10}</p>
                            )}
                            {proposal.offeredCondition && (
                              <ConditionBadge condition={proposal.offeredCondition} />
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    <div className={styles.swapIcon}>&#8644;</div>

                    <div className={styles.bookCol}>
                      <p className={styles.bookLabel}>Requested</p>
                      {requestedBook && (
                        <div className={styles.bookInfo}>
                          {getBookCoverUrl(requestedBook) && (
                            <img src={getBookCoverUrl(requestedBook)} alt={requestedBook.title} className={styles.bookCover} />
                          )}
                          <div>
                            <p className={styles.bookTitle}>{requestedBook.title}</p>
                            {getBookPrimaryAuthor(requestedBook) && <p className={styles.bookAuthor}>{getBookPrimaryAuthor(requestedBook)}</p>}
                            {(requestedBook.isbn_13 || requestedBook.isbn_10) && (
                              <p className={styles.bookIsbn}>ISBN: {requestedBook.isbn_13 || requestedBook.isbn_10}</p>
                            )}
                            {proposal.requestedCondition && (
                              <ConditionBadge condition={proposal.requestedCondition} />
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {proposal.note && (
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.25rem' }}>
                      <p className={styles.note}>&ldquo;{proposal.note}&rdquo;</p>
                      <Tooltip content="A personal message from the proposer explaining why they'd like this trade." />
                    </div>
                  )}

                  {canAct && (
                    <div className={styles.proposalActions}>
                      <Tooltip content="Accepting starts the trade. Shipping addresses will be shared with your trade partner.">
                        <button
                          className="btn btn-success btn-sm"
                          onClick={() => acceptMutation.mutate(proposal.id)}
                          disabled={acceptMutation.isPending || declineMutation.isPending}
                        >
                          Accept
                        </button>
                      </Tooltip>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => declineMutation.mutate(proposal.id)}
                        disabled={acceptMutation.isPending || declineMutation.isPending}
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
