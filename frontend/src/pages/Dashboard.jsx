import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { matches as matchesApi, myBooks as myBooksApi, proposals as proposalsApi, trades as tradesApi, users as usersApi, wishlist as wishlistApi } from '../services/api.js';
import useAuth from '../hooks/useAuth.js';
import LoadingSpinner from '../components/common/LoadingSpinner.jsx';
import Tooltip from '../components/common/Tooltip.jsx';
import styles from './Dashboard.module.css';

export default function Dashboard() {
  const { user } = useAuth();

  const { data: meData } = useQuery({
    queryKey: ['me'],
    queryFn: () => usersApi.getMe().then((r) => r.data),
    staleTime: 1000 * 60 * 5,
  });

  const { data: matchesData, isLoading: matchesLoading } = useQuery({
    queryKey: ['matches', 'pending'],
    queryFn: () => matchesApi.list({ status: 'pending', page_size: 5 }).then((r) => r.data),
  });

  const { data: proposalsData, isLoading: proposalsLoading } = useQuery({
    queryKey: ['proposals', 'received', 'pending'],
    queryFn: () =>
      proposalsApi.list({ status: 'pending', direction: 'received', page_size: 5 }).then((r) => r.data),
  });

  const { data: tradesData, isLoading: tradesLoading } = useQuery({
    queryKey: ['trades', 'active'],
    queryFn: () =>
      tradesApi.list({ status: 'active', page_size: 5 }).then((r) => r.data),
  });

  const { data: myBooksData, isLoading: myBooksLoading } = useQuery({
    queryKey: ['myBooks', 'count'],
    queryFn: () => myBooksApi.list({ page_size: 1 }).then((r) => r.data),
  });

  const { data: wishlistData, isLoading: wishlistLoading } = useQuery({
    queryKey: ['wishlist', 'count'],
    queryFn: () => wishlistApi.list({ page_size: 1 }).then((r) => r.data),
  });

  const displayUser = meData ?? user;
  const activeMatchesCount = matchesData?.count ?? 0;
  const pendingProposalsCount = proposalsData?.count ?? 0;
  const activeTradesCount = tradesData?.count ?? 0;
  const booksOfferedCount = myBooksData?.count ?? 0;
  const booksWantedCount = wishlistData?.count ?? 0;

  const recentMatches = matchesData?.results ?? [];
  const recentProposals = proposalsData?.results ?? [];
  const recentTrades = tradesData?.results ?? [];

  const isLoading = matchesLoading || proposalsLoading || tradesLoading || myBooksLoading || wishlistLoading;

  return (
    <div>
      {/* Welcome header */}
      <div className={styles.welcomeHeader}>
        <div>
          <h1 className="page-title">
            Welcome back{displayUser?.username ? `, ${displayUser.username}` : ''}!
          </h1>
          <p className="page-subtitle">Here&apos;s what&apos;s happening with your book trades.</p>
        </div>
        <div className={styles.quickActions}>
          <Link to="/my-books" className="btn btn-primary">
            + Add Book
          </Link>
          <Link to="/" className="btn btn-secondary">
            Browse Books
          </Link>
        </div>
      </div>

      {/* Summary cards */}
      {isLoading ? (
        <LoadingSpinner center size="lg" />
      ) : (
        <>
          <div className={styles.summaryGrid}>
            <Link to="/matches" className={styles.summaryCard}>
              <div className={styles.summaryIcon} style={{ background: 'var(--color-primary-light)', color: 'var(--color-primary)' }}>
                <Tooltip content="Matches are automatically found trade opportunities. Each requires both parties to accept before a trade begins." position="bottom">
                  <svg viewBox="0 0 20 20" fill="currentColor" width="24" height="24">
                    <path d="M10 1a6 6 0 00-3.815 10.631C7.237 12.5 8 13.443 8 14.456v.644a.75.75 0 00.572.729 6.016 6.016 0 002.856 0A.75.75 0 0012 15.1v-.644c0-1.013.763-1.957 1.815-2.825A6 6 0 0010 1zM8.863 17.414a.75.75 0 00-.226 1.483 9.066 9.066 0 002.726 0 .75.75 0 00-.226-1.483 7.553 7.553 0 01-2.274 0z" />
                  </svg>
                </Tooltip>
              </div>
              <div>
                <p className={styles.summaryValue}>{activeMatchesCount}</p>
                <p className={styles.summaryLabel}>Pending Matches</p>
              </div>
            </Link>

            <Link to="/proposals" className={styles.summaryCard}>
              <div className={styles.summaryIcon} style={{ background: 'var(--color-warning-light)', color: 'var(--color-warning)' }}>
                <Tooltip content="Direct trade requests sent to or from you, waiting for a response." position="bottom">
                  <svg viewBox="0 0 20 20" fill="currentColor" width="24" height="24">
                    <path fillRule="evenodd" d="M3.25 3A2.25 2.25 0 001 5.25v9.5A2.25 2.25 0 003.25 17h13.5A2.25 2.25 0 0019 14.75v-9.5A2.25 2.25 0 0016.75 3H3.25zm.943 2.25A.75.75 0 003.25 6v.5l6.75 4.2 6.75-4.2V6a.75.75 0 00-.75-.75H4.193z" clipRule="evenodd" />
                  </svg>
                </Tooltip>
              </div>
              <div>
                <p className={styles.summaryValue}>{pendingProposalsCount}</p>
                <p className={styles.summaryLabel}>Pending Proposals</p>
              </div>
            </Link>

            <Link to="/trades" className={styles.summaryCard}>
              <div className={styles.summaryIcon} style={{ background: 'var(--color-success-light)', color: 'var(--color-success)' }}>
                <Tooltip content="Confirmed trades currently in progress — books are being shipped." position="bottom">
                  <svg viewBox="0 0 20 20" fill="currentColor" width="24" height="24">
                    <path fillRule="evenodd" d="M2.5 3A1.5 1.5 0 001 4.5v4A1.5 1.5 0 002.5 10h6A1.5 1.5 0 0010 8.5v-4A1.5 1.5 0 008.5 3h-6zm11 2A1.5 1.5 0 0012 6.5v7a1.5 1.5 0 001.5 1.5h3A1.5 1.5 0 0018 13.5v-7A1.5 1.5 0 0016.5 5h-3zm-6 7A1.5 1.5 0 006 13.5v1A1.5 1.5 0 007.5 16h3a1.5 1.5 0 001.5-1.5v-1A1.5 1.5 0 0010.5 12h-3z" clipRule="evenodd" />
                  </svg>
                </Tooltip>
              </div>
              <div>
                <p className={styles.summaryValue}>{activeTradesCount}</p>
                <p className={styles.summaryLabel}>Active Trades</p>
              </div>
            </Link>

            {displayUser && (
              <div className={styles.summaryCard} style={{ cursor: 'default' }}>
                <div className={styles.summaryIcon} style={{ background: 'var(--color-gray-100)', color: 'var(--color-gray-500)' }}>
                  <Tooltip content="Total completed trades since you joined. Completing more trades increases your match capacity (up to 10 active matches)." position="bottom">
                    <svg viewBox="0 0 20 20" fill="currentColor" width="24" height="24">
                      <path d="M10 8a3 3 0 100-6 3 3 0 000 6zM3.465 14.493a1.23 1.23 0 00.41 1.412A9.957 9.957 0 0010 18c2.31 0 4.438-.784 6.131-2.1.43-.333.604-.903.408-1.41a7.002 7.002 0 00-13.074.003z" />
                    </svg>
                  </Tooltip>
                </div>
                <div>
                  <p className={styles.summaryValue}>{displayUser.total_trades ?? 0}</p>
                  <p className={styles.summaryLabel}>Total Trades</p>
                </div>
              </div>
            )}

            <Link to="/my-books" className={styles.summaryCard}>
              <div className={styles.summaryIcon} style={{ background: 'var(--color-info-light, #eff6ff)', color: 'var(--color-info, #3b82f6)' }}>
                <Tooltip content="Books you've listed as available to trade." position="bottom">
                  <svg viewBox="0 0 20 20" fill="currentColor" width="24" height="24">
                    <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z" />
                  </svg>
                </Tooltip>
              </div>
              <div>
                <p className={styles.summaryValue}>{booksOfferedCount}</p>
                <p className={styles.summaryLabel}>Books Offered</p>
              </div>
            </Link>

            <Link to="/wishlist" className={styles.summaryCard}>
              <div className={styles.summaryIcon} style={{ background: 'var(--color-purple-light, #f5f3ff)', color: 'var(--color-purple, #8b5cf6)' }}>
                <Tooltip content="Books on your wishlist you're hoping to receive in a trade." position="bottom">
                  <svg viewBox="0 0 20 20" fill="currentColor" width="24" height="24">
                    <path fillRule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clipRule="evenodd" />
                  </svg>
                </Tooltip>
              </div>
              <div>
                <p className={styles.summaryValue}>{booksWantedCount}</p>
                <p className={styles.summaryLabel}>Books Wanted</p>
              </div>
            </Link>
          </div>

          {/* Activity feed */}
          <div className={styles.activitySection}>
            {recentMatches.length > 0 && (
              <div className={styles.activityBlock}>
                <div className={styles.activityHeader}>
                  <h2 className={styles.activityTitle}>New Matches</h2>
                  <Link to="/matches" className={styles.viewAll}>View all</Link>
                </div>
                <div className={styles.activityList}>
                  {recentMatches.map((match) => (
                    <ActivityItem
                      key={match.id}
                      type="match"
                      item={match}
                    />
                  ))}
                </div>
              </div>
            )}

            {recentProposals.length > 0 && (
              <div className={styles.activityBlock}>
                <div className={styles.activityHeader}>
                  <h2 className={styles.activityTitle}>Incoming Proposals</h2>
                  <Link to="/proposals" className={styles.viewAll}>View all</Link>
                </div>
                <div className={styles.activityList}>
                  {recentProposals.map((proposal) => (
                    <ActivityItem
                      key={proposal.id}
                      type="proposal"
                      item={proposal}
                    />
                  ))}
                </div>
              </div>
            )}

            {recentTrades.length > 0 && (
              <div className={styles.activityBlock}>
                <div className={styles.activityHeader}>
                  <h2 className={styles.activityTitle}>Active Trades</h2>
                  <Link to="/trades" className={styles.viewAll}>View all</Link>
                </div>
                <div className={styles.activityList}>
                  {recentTrades.map((trade) => (
                    <ActivityItem
                      key={trade.id}
                      type="trade"
                      item={trade}
                    />
                  ))}
                </div>
              </div>
            )}

            {recentMatches.length === 0 && recentProposals.length === 0 && recentTrades.length === 0 && (
              <div className={styles.emptyActivity}>
                <p className={styles.emptyTitle}>No activity yet</p>
                <p className={styles.emptySubtitle}>
                  Add books to your have-list and wishlist to start getting matches.
                </p>
                <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem', justifyContent: 'center' }}>
                  <Link to="/my-books" className="btn btn-primary">
                    Add a Book
                  </Link>
                  <Link to="/wishlist" className="btn btn-secondary">
                    Add to Wishlist
                  </Link>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export function ActivityItem({ type, item }) {
  const getTitle = () => {
    if (type === 'match') {
      const book = item.your_book?.book ?? item.book;
      return book?.title ?? 'Book match';
    }
    if (type === 'proposal') {
      const book = item.offered_book?.book ?? item.book;
      return book?.title ?? 'Trade proposal';
    }
    if (type === 'trade') {
      const book = item.initiator_book?.book ?? item.book;
      return book?.title ?? 'Trade';
    }
    return 'Activity';
  };

  const getSubtitle = () => {
    if (type === 'match') return `Partner: ${item.partner?.username ?? 'Unknown'}`;
    if (type === 'proposal') return `From: ${item.proposer?.username ?? 'Unknown'}`;
    if (type === 'trade') return `Status: ${item.status ?? 'active'}`;
    return '';
  };

  const getLink = () => {
    if (type === 'match') return '/matches';
    if (type === 'proposal') return '/proposals';
    if (type === 'trade') return `/trades/${item.id}`;
    return '/';
  };

  const getTypeLabel = () => {
    if (type === 'match') return { label: 'Match', cls: 'badge-blue' };
    if (type === 'proposal') return { label: 'Proposal', cls: 'badge-amber' };
    if (type === 'trade') return { label: 'Trade', cls: 'badge-green' };
    return { label: type, cls: 'badge-gray' };
  };

  const { label, cls } = getTypeLabel();

  return (
    <Link to={getLink()} className={styles.activityItem}>
      <div className={styles.activityContent}>
        <p className={styles.activityItemTitle}>{getTitle()}</p>
        <p className={styles.activityItemSub}>{getSubtitle()}</p>
      </div>
      <span className={`badge ${cls}`}>{label}</span>
    </Link>
  );
}
