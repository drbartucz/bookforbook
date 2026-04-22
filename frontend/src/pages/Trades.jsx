import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { trades as tradesApi } from '../services/api.js';
import LoadingSpinner from '../components/common/LoadingSpinner.jsx';
import ErrorMessage from '../components/common/ErrorMessage.jsx';
import Pagination from '../components/common/Pagination.jsx';
import { format } from 'date-fns';
import { getBookCoverUrl, getBookPrimaryAuthor } from '../utils/book.js';
import styles from './Trades.module.css';

const PAGE_SIZE = 15;

const STATUS_TABS = [
  { value: '', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'completed', label: 'Completed' },
];

const TRADE_STATUS_CONFIG = {
  confirmed: { label: 'Confirmed', cls: 'badge-blue' },
  shipping: { label: 'Shipping', cls: 'badge-amber' },
  one_received: { label: 'Partially Received', cls: 'badge-amber' },
  completed: { label: 'Completed', cls: 'badge-green' },
  disputed: { label: 'Disputed', cls: 'badge-red' },
  cancelled: { label: 'Cancelled', cls: 'badge-gray' },
};

export default function Trades() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('active');

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['trades', statusFilter, page],
    queryFn: () => {
      const params = { page, page_size: PAGE_SIZE };
      if (statusFilter) params.status = statusFilter;
      return tradesApi.list(params).then((r) => r.data);
    },
  });

  const items = data?.results ?? [];
  const totalPages = Math.ceil((data?.count ?? 0) / PAGE_SIZE);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Trades</h1>
        <p className="page-subtitle">All your ongoing and completed book trades.</p>
      </div>

      <div className={styles.tabs}>
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            className={`${styles.tab} ${statusFilter === tab.value ? styles.activeTab : ''}`}
            onClick={() => { setStatusFilter(tab.value); setPage(1); }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <LoadingSpinner center size="lg" />
      ) : isError ? (
        <ErrorMessage error={error} onRetry={refetch} />
      ) : items.length === 0 ? (
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>No trades found</p>
          <p className={styles.emptySubtitle}>
            Trades are created when you and a match partner both accept. Check your matches!
          </p>
          <Link to="/matches" className="btn btn-primary" style={{ marginTop: '1rem' }}>
            View Matches
          </Link>
        </div>
      ) : (
        <>
          <div className={styles.tradeList}>
            {items.map((trade) => {
              const statusConfig = TRADE_STATUS_CONFIG[trade.status] ?? { label: trade.status, cls: 'badge-gray' };
              const myBook = trade.initiator_book?.book ?? trade.my_book?.book;
              const theirBook = trade.responder_book?.book ?? trade.their_book?.book;
              const partner = trade.partner ?? trade.other_user;

              return (
                <Link key={trade.id} to={`/trades/${trade.id}`} className={`card ${styles.tradeCard}`}>
                  <div className={styles.tradeHeader}>
                    <div className={styles.tradeId}>Trade #{trade.id}</div>
                    <span className={`badge ${statusConfig.cls}`}>{statusConfig.label}</span>
                  </div>

                  <div className={styles.tradeBooks}>
                    <div className={styles.tradeBook}>
                      {getBookCoverUrl(myBook) && (
                        <img src={getBookCoverUrl(myBook)} alt={myBook.title} className={styles.tradeCover} />
                      )}
                      <div className={styles.tradeBookInfo}>
                        <p className={styles.tradeBookLabel}>You send</p>
                        <p className={styles.tradeBookTitle}>{myBook?.title ?? 'Unknown'}</p>
                        {getBookPrimaryAuthor(myBook) && <p className={styles.tradeBookAuthor}>{getBookPrimaryAuthor(myBook)}</p>}
                      </div>
                    </div>

                    <span className={styles.tradeSwap}>&#8646;</span>

                    <div className={styles.tradeBook}>
                      {getBookCoverUrl(theirBook) && (
                        <img src={getBookCoverUrl(theirBook)} alt={theirBook.title} className={styles.tradeCover} />
                      )}
                      <div className={styles.tradeBookInfo}>
                        <p className={styles.tradeBookLabel}>You receive</p>
                        <p className={styles.tradeBookTitle}>{theirBook?.title ?? 'Unknown'}</p>
                        {getBookPrimaryAuthor(theirBook) && <p className={styles.tradeBookAuthor}>{getBookPrimaryAuthor(theirBook)}</p>}
                      </div>
                    </div>
                  </div>

                  <div className={styles.tradeMeta}>
                    {partner && (
                      <span className={styles.tradePartner}>@{partner.username}</span>
                    )}
                    {trade.created_at && (
                      <span className={styles.tradeDate}>
                        {format(new Date(trade.created_at), 'MMM d, yyyy')}
                      </span>
                    )}
                    <span className={styles.viewLink}>View details &rarr;</span>
                  </div>
                </Link>
              );
            })}
          </div>
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
