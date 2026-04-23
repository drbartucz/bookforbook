import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { matches as matchesApi } from '../services/api.js';
import LoadingSpinner from '../components/common/LoadingSpinner.jsx';
import ErrorMessage from '../components/common/ErrorMessage.jsx';
import ConditionBadge from '../components/common/ConditionBadge.jsx';
import Pagination from '../components/common/Pagination.jsx';
import { getBookCoverUrl, getBookPrimaryAuthor } from '../utils/book.js';
import useAuth from '../hooks/useAuth.js';
import { mapMatchForCard } from '../adapters/matches.js';
import styles from './Matches.module.css';

const PAGE_SIZE = 15;

const STATUS_TABS = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'declined', label: 'Declined' },
];

const STATUS_CONFIG = {
  pending: { label: 'Pending', cls: 'badge-amber' },
  accepted: { label: 'Accepted', cls: 'badge-green' },
  declined: { label: 'Declined', cls: 'badge-red' },
  expired: { label: 'Expired', cls: 'badge-gray' },
};

export default function Matches() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [actionError, setActionError] = useState(null);
  const [requiresAddressVerification, setRequiresAddressVerification] = useState(false);
  const [verificationUrl, setVerificationUrl] = useState('/account');

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['matches', statusFilter, page],
    queryFn: () => {
      const params = { page, page_size: PAGE_SIZE };
      if (statusFilter) params.status = statusFilter;
      return matchesApi.list(params).then((r) => r.data);
    },
  });

  const acceptMutation = useMutation({
    mutationFn: (id) => matchesApi.accept(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['matches'] });
      setActionError(null);
      setRequiresAddressVerification(false);
      setVerificationUrl('/account');
    },
    onError: (err) => {
      const responseData = err?.response?.data;
      setActionError(responseData?.detail || 'Failed to accept match.');
      if (responseData?.code === 'address_verification_required') {
        setRequiresAddressVerification(true);
        setVerificationUrl(responseData?.verification_url || '/account');
      } else {
        setRequiresAddressVerification(false);
        setVerificationUrl('/account');
      }
    },
  });

  const declineMutation = useMutation({
    mutationFn: (id) => matchesApi.decline(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['matches'] });
      setActionError(null);
      setRequiresAddressVerification(false);
      setVerificationUrl('/account');
    },
    onError: (err) => {
      setActionError(err?.response?.data?.detail || 'Failed to decline match.');
    },
  });

  const items = (data?.results ?? []).map((match) => mapMatchForCard(match, user?.id));
  const totalPages = Math.ceil((data?.count ?? 0) / PAGE_SIZE);

  function handleTabChange(val) {
    setStatusFilter(val);
    setPage(1);
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Matches</h1>
        <p className="page-subtitle">
          A match occurs when you have a book someone wants, and they have a book you want.
        </p>
      </div>

      {/* Tabs */}
      <div className={styles.tabs}>
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            className={`${styles.tab} ${statusFilter === tab.value ? styles.activeTab : ''}`}
            onClick={() => handleTabChange(tab.value)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {actionError && (
        <div className="alert alert-error" style={{ marginBottom: '1rem' }}>
          <div>{actionError}</div>
          {requiresAddressVerification && verificationUrl && (
            <Link
              to={verificationUrl}
              className="btn btn-secondary"
              style={{ marginTop: '0.75rem', display: 'inline-flex' }}
            >
              Verify address now
            </Link>
          )}
        </div>
      )}

      {isLoading ? (
        <LoadingSpinner center size="lg" />
      ) : isError ? (
        <ErrorMessage error={error} onRetry={refetch} />
      ) : items.length === 0 ? (
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>
            {statusFilter === 'pending' ? 'No pending matches' : 'No matches found'}
          </p>
          <p className={styles.emptySubtitle}>
            Matches are created automatically when your books line up with other users&apos; wishlists.
            Make sure your have-list and wishlist are up to date.
          </p>
        </div>
      ) : (
        <>
          <div className={styles.matchList}>
            {items.map((match) => (
              <MatchCard
                key={match.id}
                match={match}
                onAccept={() => acceptMutation.mutate(match.id)}
                onDecline={() => declineMutation.mutate(match.id)}
                accepting={acceptMutation.isPending && acceptMutation.variables === match.id}
                declining={declineMutation.isPending && declineMutation.variables === match.id}
              />
            ))}
          </div>
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}

function MatchCard({ match, onAccept, onDecline, accepting, declining }) {
  const statusConfig = STATUS_CONFIG[match.status] ?? { label: match.status, cls: 'badge-gray' };

  const yourBook = match.yourBook;
  const theirBook = match.theirBook;
  const partner = match.partner;

  return (
    <div className={`card ${styles.matchCard}`}>
      <div className={styles.matchHeader}>
        <div className={styles.matchId}>Match #{match.id}</div>
        <span className={`badge ${statusConfig.cls}`}>{statusConfig.label}</span>
      </div>

      <div className={styles.exchange}>
        {/* You give */}
        <div className={styles.exchangeBook}>
          <p className={styles.exchangeLabel}>You give</p>
          {yourBook ? (
            <>
              {getBookCoverUrl(yourBook) && (
                <img src={getBookCoverUrl(yourBook)} alt={yourBook.title} className={styles.exchangeCover} />
              )}
              <p className={styles.exchangeTitle}>{yourBook.title}</p>
              {getBookPrimaryAuthor(yourBook) && <p className={styles.exchangeAuthor}>{getBookPrimaryAuthor(yourBook)}</p>}
              {match.yourCondition && (
                <ConditionBadge condition={match.yourCondition} />
              )}
            </>
          ) : (
            <p className={styles.exchangeUnknown}>Book info unavailable</p>
          )}
        </div>

        {/* Arrow */}
        <div className={styles.exchangeArrow}>
          <svg viewBox="0 0 20 20" fill="currentColor" width="20" height="20">
            <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
          </svg>
          <svg viewBox="0 0 20 20" fill="currentColor" width="20" height="20" style={{ transform: 'scaleX(-1)' }}>
            <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
          </svg>
        </div>

        {/* You receive */}
        <div className={styles.exchangeBook}>
          <p className={styles.exchangeLabel}>You receive</p>
          {theirBook ? (
            <>
              {getBookCoverUrl(theirBook) && (
                <img src={getBookCoverUrl(theirBook)} alt={theirBook.title} className={styles.exchangeCover} />
              )}
              <p className={styles.exchangeTitle}>{theirBook.title}</p>
              {getBookPrimaryAuthor(theirBook) && <p className={styles.exchangeAuthor}>{getBookPrimaryAuthor(theirBook)}</p>}
              {match.theirCondition && (
                <ConditionBadge condition={match.theirCondition} />
              )}
            </>
          ) : (
            <p className={styles.exchangeUnknown}>Book info unavailable</p>
          )}
        </div>
      </div>

      {partner && (
        <p className={styles.partnerInfo}>
          Trade partner:{' '}
          <a href={`/profile/${partner.id}`} className={styles.partnerLink}>
            @{partner.username}
          </a>
          {partner.avg_recent_rating && (
            <span className={styles.partnerRating}>
              {' '}&bull; {Number(partner.avg_recent_rating).toFixed(1)} ★
            </span>
          )}
        </p>
      )}

      {match.status === 'pending' && (
        <div className={styles.matchActions}>
          <button
            className="btn btn-success"
            onClick={onAccept}
            disabled={accepting || declining}
          >
            {accepting ? 'Accepting...' : 'Accept Match'}
          </button>
          <button
            className="btn btn-secondary"
            onClick={onDecline}
            disabled={accepting || declining}
          >
            {declining ? 'Declining...' : 'Decline'}
          </button>
        </div>
      )}
    </div>
  );
}
