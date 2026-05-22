import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { community as communityApi } from '../services/api.js';
import LoadingSpinner from '../components/common/LoadingSpinner.jsx';
import ErrorMessage from '../components/common/ErrorMessage.jsx';
import Pagination from '../components/common/Pagination.jsx';
import { parsePaginatedResponse } from '../utils/pagination.js';
import styles from './Community.module.css';

const PAGE_SIZE = 24;

const SORT_OPTIONS = [
  { value: '-karma_score', label: 'Karma' },
  { value: '-total_trades', label: 'Most Trades' },
  { value: '-gifts_given_count', label: 'Most Generous' },
  { value: '-avg_recent_rating', label: 'Highest Rated' },
  { value: 'created_at', label: 'Newest Members' },
];

const BADGE_FILTER_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'giver', label: 'Top Givers' },
  { value: 'trader', label: 'Top Traders' },
];

const GIVER_BADGE_LABELS = {
  top_10: 'Top 10% Giver',
  top_25: 'Top 25% Giver',
};

const TRADER_BADGE_LABELS = {
  top_10: 'Top 10% Trader',
  top_25: 'Top 25% Trader',
};

export default function Community() {
  const [page, setPage] = useState(1);
  const [ordering, setOrdering] = useState('-karma_score');
  const [badgeFilter, setBadgeFilter] = useState('');
  const [hasBooks, setHasBooks] = useState(false);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');

  function buildParams() {
    const params = {
      page,
      page_size: PAGE_SIZE,
      ordering,
    };
    if (search) params.search = search;
    if (badgeFilter === 'giver') params.giver_badge = 'top_10';
    if (badgeFilter === 'trader') params.trader_badge = 'top_10';
    if (hasBooks) params.has_books = 'true';
    return params;
  }

  const params = buildParams();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['community', params],
    queryFn: () => communityApi.list(params).then((r) => r.data),
    keepPreviousData: true,
  });

  const { results: users, count } = parsePaginatedResponse(data);
  const totalPages = count != null ? Math.ceil(count / PAGE_SIZE) : 1;

  function handleSortChange(e) {
    setOrdering(e.target.value);
    setPage(1);
  }

  function handleBadgeFilter(value) {
    setBadgeFilter(value);
    setPage(1);
  }

  function handleHasBooksToggle() {
    setHasBooks((prev) => !prev);
    setPage(1);
  }

  function handleSearchSubmit(e) {
    e.preventDefault();
    setSearch(searchInput.trim());
    setPage(1);
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.heading}>Community</h1>
        <p className={styles.subtitle}>Discover active traders and generous givers</p>
      </div>

      <div className={styles.controls}>
        <form className={styles.searchForm} onSubmit={handleSearchSubmit}>
          <input
            type="text"
            className={`form-input ${styles.searchInput}`}
            placeholder="Search by username..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            aria-label="Search users"
          />
          <button type="submit" className="btn btn-primary btn-sm">
            Search
          </button>
          {search && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setSearch('');
                setSearchInput('');
                setPage(1);
              }}
            >
              Clear
            </button>
          )}
        </form>

        <div className={styles.filtersRow}>
          <select
            className={`form-input ${styles.sortSelect}`}
            value={ordering}
            onChange={handleSortChange}
            aria-label="Sort by"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          <div className={styles.badgeFilterGroup}>
            {BADGE_FILTER_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`btn btn-sm ${badgeFilter === opt.value ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => handleBadgeFilter(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <label className={styles.toggleLabel}>
            <input
              type="checkbox"
              checked={hasBooks}
              onChange={handleHasBooksToggle}
              className={styles.toggleCheckbox}
            />
            Has books available
          </label>
        </div>
      </div>

      {isLoading && <LoadingSpinner center size="lg" />}
      {isError && <ErrorMessage error={error} />}

      {!isLoading && !isError && users.length === 0 && (
        <div className={styles.emptyState}>
          <p className={styles.emptyText}>No users found matching your filters.</p>
        </div>
      )}

      {!isLoading && !isError && users.length > 0 && (
        <>
          <div className={styles.grid}>
            {users.map((u) => (
              <UserCard key={u.id} user={u} />
            ))}
          </div>

          {totalPages > 1 && (
            <Pagination
              currentPage={page}
              totalPages={totalPages}
              onPageChange={setPage}
            />
          )}
        </>
      )}
    </div>
  );
}

function UserCard({ user }) {
  const memberYear = user.created_at
    ? new Date(user.created_at).getFullYear()
    : null;

  return (
    <div className={styles.card}>
      <div className={styles.cardAvatar}>
        {user.username?.[0]?.toUpperCase() ?? 'U'}
      </div>

      <div className={styles.cardBody}>
        <Link to={`/profile/${user.id}`} className={styles.cardUsername}>
          @{user.username}
        </Link>

        <div className={styles.karmaRow}>
          <span className={styles.karmaIcon}>✦</span>
          <span className={styles.karmaValue}>{user.karma ?? 0}</span>
          <span className={styles.karmaLabel}>karma</span>
        </div>

        <div className={styles.badgeRow}>
          {user.giver_badge && (
            <span className={`${styles.badgeChip} ${styles.badgeChipAmber}`}>
              {GIVER_BADGE_LABELS[user.giver_badge] ?? user.giver_badge}
            </span>
          )}
          {user.trader_badge && (
            <span className={`${styles.badgeChip} ${styles.badgeChipBlue}`}>
              {TRADER_BADGE_LABELS[user.trader_badge] ?? user.trader_badge}
            </span>
          )}
        </div>

        <div className={styles.statsRow}>
          <span className={styles.statItem}>
            {user.total_trades ?? 0} trades
          </span>
          {user.avg_recent_rating != null && (
            <span className={styles.statItem}>
              {Number(user.avg_recent_rating).toFixed(1)} ★
            </span>
          )}
          {memberYear && (
            <span className={styles.statItem}>Since {memberYear}</span>
          )}
        </div>
      </div>
    </div>
  );
}
