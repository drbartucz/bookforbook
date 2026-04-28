import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { browse, wishlist as wishlistApi } from '../services/api.js';
import useAuth from '../hooks/useAuth.js';
import useDebounce from '../hooks/useDebounce.js';
import BookCard from '../components/common/BookCard.jsx';
import LoadingSpinner from '../components/common/LoadingSpinner.jsx';
import ErrorMessage from '../components/common/ErrorMessage.jsx';
import Pagination from '../components/common/Pagination.jsx';
import Tooltip from '../components/common/Tooltip.jsx';
import { getBookIsbn } from '../utils/book.js';
import styles from './Home.module.css';

const PAGE_SIZE = 20;

const CONDITION_OPTIONS = [
  { value: '', label: 'Any condition' },
  { value: 'like_new', label: 'Like New' },
  { value: 'very_good', label: 'Very Good' },
  { value: 'good', label: 'Good' },
  { value: 'acceptable', label: 'Acceptable' },
];

export default function Home() {
  const { isAuthenticated } = useAuth();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState('offer');

  // Offer tab state
  const [offerPage, setOfferPage] = useState(1);
  const [offerSearch, setOfferSearch] = useState('');
  const [offerCondition, setOfferCondition] = useState('');
  const [addedToWishlist, setAddedToWishlist] = useState(new Set());

  // Wanted tab state
  const [wantedPage, setWantedPage] = useState(1);
  const [wantedSearch, setWantedSearch] = useState('');

  const debouncedOfferSearch = useDebounce(offerSearch, 400);
  const debouncedWantedSearch = useDebounce(wantedSearch, 400);

  const offerQuery = useQuery({
    queryKey: ['browse', 'available', debouncedOfferSearch, offerCondition, offerPage],
    queryFn: async () => {
      const params = { page: offerPage, page_size: PAGE_SIZE };
      const trimmedSearch = debouncedOfferSearch.trim();
      if (trimmedSearch) params.q = trimmedSearch;
      if (offerCondition) params.condition = offerCondition;
      const res = await browse.available(params);
      return res.data;
    },
    keepPreviousData: true,
    staleTime: 1000 * 60 * 2,
  });

  const wantedQuery = useQuery({
    queryKey: ['browse', 'wanted', debouncedWantedSearch, wantedPage],
    queryFn: async () => {
      const params = { page: wantedPage, page_size: PAGE_SIZE };
      const trimmedSearch = debouncedWantedSearch.trim();
      if (trimmedSearch) params.q = trimmedSearch;
      const res = await browse.wanted(params);
      return res.data;
    },
    keepPreviousData: true,
    staleTime: 1000 * 60 * 2,
  });

  const addToWishlistMutation = useMutation({
    mutationFn: ({ isbn }) => wishlistApi.add({ isbn }),
    onSuccess: (_, variables) => {
      setAddedToWishlist((prev) => new Set([...prev, variables.isbn]));
      queryClient.invalidateQueries({ queryKey: ['wishlist'] });
    },
  });

  const offerBooks = offerQuery.data?.results ?? [];
  const offerTotal = offerQuery.data?.count ?? 0;
  const offerTotalPages = Math.ceil(offerTotal / PAGE_SIZE);

  const wantedBooks = wantedQuery.data?.results ?? [];
  const wantedTotal = wantedQuery.data?.count ?? 0;
  const wantedTotalPages = Math.ceil(wantedTotal / PAGE_SIZE);

  function handleOfferSearchChange(e) {
    setOfferSearch(e.target.value);
    setOfferPage(1);
  }

  function handleOfferConditionChange(e) {
    setOfferCondition(e.target.value);
    setOfferPage(1);
  }

  function handleWantedSearchChange(e) {
    setWantedSearch(e.target.value);
    setWantedPage(1);
  }

  function handleTabChange(tab) {
    setActiveTab(tab);
  }

  return (
    <div>
      {/* Hero */}
      <div className={styles.hero}>
        <h1 className={styles.heroTitle}>Trade books, not money</h1>
        <p className={styles.heroSubtitle}>
          What are you going to do with all those books you've read, or are never going to read? Trade them for ones you want, or donate them to a library or used bookstore!
        </p>
        {!isAuthenticated && (
          <div className={styles.heroActions}>
            <Link to="/register" className="btn btn-primary btn-lg">
              Register
            </Link>
            <Link to="/login" className="btn btn-secondary btn-lg">
              Sign in
            </Link>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className={styles.tabs} role="tablist" aria-label="Browse books">
        <button
          role="tab"
          aria-selected={activeTab === 'offer'}
          className={`${styles.tab} ${activeTab === 'offer' ? styles.tabActive : ''}`}
          onClick={() => handleTabChange('offer')}
        >
          Books on Offer
          {offerTotal > 0 && (
            <span className={styles.tabCount}>{offerTotal}</span>
          )}
        </button>
        <button
          role="tab"
          aria-selected={activeTab === 'wanted'}
          className={`${styles.tab} ${activeTab === 'wanted' ? styles.tabActive : ''}`}
          onClick={() => handleTabChange('wanted')}
        >
          Books Wanted
          {wantedTotal > 0 && (
            <span className={styles.tabCount}>{wantedTotal}</span>
          )}
        </button>
      </div>

      {/* ── ON OFFER TAB ─────────────────────────────────────────── */}
      {activeTab === 'offer' && (
        <div role="tabpanel" aria-label="Books on Offer">
          {/* Filters */}
          <div className={styles.filters}>
            <div className={styles.searchWrapper}>
              <svg className={styles.searchIcon} viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
                <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clipRule="evenodd" />
              </svg>
              <input
                type="search"
                className={`form-input ${styles.searchInput}`}
                placeholder="Search by title, author, or ISBN..."
                value={offerSearch}
                onChange={handleOfferSearchChange}
                aria-label="Search books"
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
              <select
                className={`form-input ${styles.conditionSelect}`}
                value={offerCondition}
                onChange={handleOfferConditionChange}
                aria-label="Filter by condition"
              >
                {CONDITION_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <Tooltip content="Show only books listed at exactly this condition. Use 'Any condition' to see all." />
            </div>
          </div>

          {!offerQuery.isLoading && !offerQuery.isError && (
            <div className={styles.resultsHeader}>
              <p className={styles.resultsCount}>
                {offerTotal === 0
                  ? 'No books found'
                  : `${offerTotal} book${offerTotal === 1 ? '' : 's'} available`}
              </p>
            </div>
          )}

          {offerQuery.isLoading ? (
            <LoadingSpinner center size="lg" label="Loading available books..." />
          ) : offerQuery.isError ? (
            <ErrorMessage error={offerQuery.error} onRetry={offerQuery.refetch} />
          ) : offerBooks.length === 0 ? (
            <div className={styles.empty}>
              <p className={styles.emptyTitle}>No books found</p>
              <p className={styles.emptySubtitle}>
                {offerSearch || offerCondition
                  ? 'Try adjusting your search or filters.'
                  : 'Be the first to add a book! Sign up and list your books.'}
              </p>
              {!isAuthenticated && (
                <Link to="/register" className="btn btn-primary" style={{ marginTop: '1rem' }}>
                  Start trading
                </Link>
              )}
            </div>
          ) : (
            <>
              <div className={`grid grid-cols-1 grid-sm-2 grid-md-3 grid-lg-4 ${styles.grid}`}>
                {offerBooks.map((item) => {
                  const isbn = getBookIsbn(item);
                  const alreadyAdded = isbn && addedToWishlist.has(isbn);

                  return (
                    <BookCard
                      key={item.id}
                      book={item}
                      copyCount={item.copy_count ?? 1}
                      onAction={
                        isAuthenticated && !alreadyAdded
                          ? () => addToWishlistMutation.mutate({ isbn })
                          : undefined
                      }
                      actionLabel={alreadyAdded ? 'Added!' : 'Want this'}
                      actionTooltip="Adds this book to your wishlist. You'll be matched automatically when someone who wants a book you own lists one you want."
                      actionLoading={
                        addToWishlistMutation.isPending &&
                        addToWishlistMutation.variables?.isbn === isbn
                      }
                    />
                  );
                })}
              </div>
              <Pagination
                page={offerPage}
                totalPages={offerTotalPages}
                onPageChange={setOfferPage}
                disabled={offerQuery.isLoading}
              />
            </>
          )}
        </div>
      )}

      {/* ── WANTED TAB ───────────────────────────────────────────── */}
      {activeTab === 'wanted' && (
        <div role="tabpanel" aria-label="Books Wanted">
          {/* Search */}
          <div className={styles.filters}>
            <div className={styles.searchWrapper}>
              <svg className={styles.searchIcon} viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
                <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clipRule="evenodd" />
              </svg>
              <input
                type="search"
                className={`form-input ${styles.searchInput}`}
                placeholder="Search by title, author, or ISBN..."
                value={wantedSearch}
                onChange={handleWantedSearchChange}
                aria-label="Search wanted books"
              />
            </div>
          </div>

          {!wantedQuery.isLoading && !wantedQuery.isError && (
            <div className={styles.resultsHeader}>
              <p className={styles.resultsCount}>
                {wantedTotal === 0
                  ? 'No books found'
                  : `${wantedTotal} book${wantedTotal === 1 ? '' : 's'} wanted`}
              </p>
            </div>
          )}

          {wantedQuery.isLoading ? (
            <LoadingSpinner center size="lg" label="Loading wanted books..." />
          ) : wantedQuery.isError ? (
            <ErrorMessage error={wantedQuery.error} onRetry={wantedQuery.refetch} />
          ) : wantedBooks.length === 0 ? (
            <div className={styles.empty}>
              <p className={styles.emptyTitle}>No books found</p>
              <p className={styles.emptySubtitle}>
                {wantedSearch
                  ? 'Try adjusting your search.'
                  : 'No one has added books to their wishlist yet. Sign up and add the books you want!'}
              </p>
              {!isAuthenticated && (
                <Link to="/register" className="btn btn-primary" style={{ marginTop: '1rem' }}>
                  Start trading
                </Link>
              )}
            </div>
          ) : (
            <>
              <div className={`grid grid-cols-1 grid-sm-2 grid-md-3 grid-lg-4 ${styles.grid}`}>
                {wantedBooks.map((item) => (
                  <BookCard
                    key={item.id}
                    book={item}
                    extra={
                      item.want_count > 1
                        ? <span className="badge badge-blue">{item.want_count} people want this</span>
                        : <span className="badge badge-blue">1 person wants this</span>
                    }
                  />
                ))}
              </div>
              <Pagination
                page={wantedPage}
                totalPages={wantedTotalPages}
                onPageChange={setWantedPage}
                disabled={wantedQuery.isLoading}
              />
            </>
          )}
        </div>
      )}
    </div>
  );
}
