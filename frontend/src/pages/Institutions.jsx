import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { institutions as institutionsApi } from '../services/api.js';
import useDebounce from '../hooks/useDebounce.js';
import LoadingSpinner from '../components/common/LoadingSpinner.jsx';
import ErrorMessage from '../components/common/ErrorMessage.jsx';
import Pagination from '../components/common/Pagination.jsx';
import styles from './Institutions.module.css';

const PAGE_SIZE = 20;

const TYPE_FILTERS = [
  { value: '', label: 'All types' },
  { value: 'library', label: 'Libraries' },
  { value: 'bookstore', label: 'Bookstores' },
  { value: 'school', label: 'Schools' },
  { value: 'other', label: 'Other' },
];

export default function Institutions() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');

  const debouncedSearch = useDebounce(search, 400);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['institutions', debouncedSearch, typeFilter, page],
    queryFn: () => {
      const params = { page, page_size: PAGE_SIZE };
      if (debouncedSearch) params.search = debouncedSearch;
      if (typeFilter) params.institution_type = typeFilter;
      return institutionsApi.list(params).then((r) => r.data);
    },
    staleTime: 1000 * 60 * 5,
  });

  const items = data?.results ?? [];
  const totalPages = Math.ceil((data?.count ?? 0) / PAGE_SIZE);

  function handleSearch(e) {
    setSearch(e.target.value);
    setPage(1);
  }

  function handleTypeChange(e) {
    setTypeFilter(e.target.value);
    setPage(1);
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Institutions</h1>
        <p className="page-subtitle">
          Browse verified libraries and bookstores that accept book donations and trades.
        </p>
      </div>

      {/* Filters */}
      <div className={styles.filters}>
        <div className={styles.searchWrapper}>
          <svg className={styles.searchIcon} viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
            <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clipRule="evenodd" />
          </svg>
          <input
            type="search"
            className={`form-input ${styles.searchInput}`}
            placeholder="Search by name or location..."
            value={search}
            onChange={handleSearch}
            aria-label="Search institutions"
          />
        </div>
        <select
          className={`form-input ${styles.typeSelect}`}
          value={typeFilter}
          onChange={handleTypeChange}
          aria-label="Filter by type"
        >
          {TYPE_FILTERS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <LoadingSpinner center size="lg" />
      ) : isError ? (
        <ErrorMessage error={error} onRetry={refetch} />
      ) : items.length === 0 ? (
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>No institutions found</p>
          <p className={styles.emptySubtitle}>
            {search || typeFilter
              ? 'Try adjusting your search filters.'
              : 'No verified institutions yet. Check back soon.'}
          </p>
        </div>
      ) : (
        <>
          <p className={styles.count}>
            {data?.count ?? 0} institution{(data?.count ?? 0) === 1 ? '' : 's'}
          </p>
          <div className={styles.institutionGrid}>
            {items.map((institution) => (
              <InstitutionCard key={institution.id} institution={institution} />
            ))}
          </div>
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}

function InstitutionCard({ institution }) {
  const user = institution.user ?? institution;
  const profileId = user.id ?? institution.id;

  return (
    <div className={`card ${styles.institutionCard}`}>
      <div className={styles.institutionAvatar}>
        {(user.username ?? institution.name ?? 'I')[0].toUpperCase()}
      </div>
      <div className={styles.institutionInfo}>
        <div className={styles.institutionNameRow}>
          <h2 className={styles.institutionName}>
            {institution.display_name ?? institution.name ?? user.username}
          </h2>
          {institution.is_verified && (
            <span className="badge badge-green">Verified</span>
          )}
          {institution.institution_type && (
            <span className="badge badge-blue">
              {institution.institution_type}
            </span>
          )}
        </div>
        {institution.location && (
          <p className={styles.institutionLocation}>
            <svg viewBox="0 0 20 20" fill="currentColor" width="13" height="13">
              <path fillRule="evenodd" d="M9.69 18.933l.003.001C9.89 19.02 10 19 10 19s.11.02.308-.066l.002-.001.006-.003.018-.008a5.741 5.741 0 00.281-.14c.186-.096.446-.24.757-.433.62-.384 1.445-.966 2.274-1.765C15.302 14.988 17 12.493 17 9A7 7 0 103 9c0 3.492 1.698 5.988 3.355 7.584a13.731 13.731 0 002.273 1.765 11.842 11.842 0 00.976.544l.062.029.018.008.006.003zM10 11.25a2.25 2.25 0 100-4.5 2.25 2.25 0 000 4.5z" clipRule="evenodd" />
            </svg>
            {institution.location}
          </p>
        )}
        {institution.bio && (
          <p className={styles.institutionBio}>{institution.bio}</p>
        )}
        <div className={styles.institutionStats}>
          {institution.total_trades != null && (
            <span className={styles.institutionStat}>
              {institution.total_trades} trades
            </span>
          )}
          {institution.offered_count != null && (
            <span className={styles.institutionStat}>
              {institution.offered_count} books offered
            </span>
          )}
          {institution.wanted_count != null && (
            <span className={styles.institutionStat}>
              {institution.wanted_count} books wanted
            </span>
          )}
          {institution.avg_recent_rating != null && (
            <span className={styles.institutionStat}>
              {Number(institution.avg_recent_rating).toFixed(1)} ★
            </span>
          )}
        </div>
      </div>
      <Link
        to={`/profile/${profileId}`}
        className={`btn btn-secondary btn-sm ${styles.viewBtn}`}
      >
        View Profile &rarr;
      </Link>
    </div>
  );
}
