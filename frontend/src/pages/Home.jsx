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
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [condition, setCondition] = useState('');
  const [addedToWishlist, setAddedToWishlist] = useState(new Set());

  const debouncedSearch = useDebounce(search, 400);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['browse', 'available', debouncedSearch, condition, page],
    queryFn: async () => {
      const params = { page, page_size: PAGE_SIZE };
      const trimmedSearch = debouncedSearch.trim();
      if (trimmedSearch) params.q = trimmedSearch;
      if (condition) params.condition = condition;
      const res = await browse.available(params);
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

  const books = data?.results ?? [];
  const totalCount = data?.count ?? 0;
  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  function handleSearchChange(e) {
    setSearch(e.target.value);
    setPage(1);
  }

  function handleConditionChange(e) {
    setCondition(e.target.value);
    setPage(1);
  }

  return (
    <div>
      {/* Hero */}
      <div className={styles.hero}>
        <h1 className={styles.heroTitle}>Trade books, not money</h1>
        <p className={styles.heroSubtitle}>
          Browse books offered by readers across continental USA. Find what you want and offer what you have.
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
            value={search}
            onChange={handleSearchChange}
            aria-label="Search books"
          />
        </div>
        <select
          className={`form-input ${styles.conditionSelect}`}
          value={condition}
          onChange={handleConditionChange}
          aria-label="Filter by condition"
        >
          {CONDITION_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Results header */}
      {!isLoading && !isError && (
        <div className={styles.resultsHeader}>
          <p className={styles.resultsCount}>
            {totalCount === 0
              ? 'No books found'
              : `${totalCount} book${totalCount === 1 ? '' : 's'} available`}
          </p>
        </div>
      )}

      {/* Content */}
      {isLoading ? (
        <LoadingSpinner center size="lg" label="Loading available books..." />
      ) : isError ? (
        <ErrorMessage error={error} onRetry={refetch} />
      ) : books.length === 0 ? (
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>No books found</p>
          <p className={styles.emptySubtitle}>
            {search || condition
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
            {books.map((item) => {
              const book = item.book ?? item;
              const owner = item.owner ?? item.user;
              const isbn = getBookIsbn(book);
              const alreadyAdded = isbn && addedToWishlist.has(isbn);

              return (
                <BookCard
                  key={item.id}
                  book={book}
                  owner={owner}
                  onAction={
                    isAuthenticated && !alreadyAdded
                      ? () =>
                        addToWishlistMutation.mutate({ isbn })
                      : undefined
                  }
                  actionLabel={alreadyAdded ? 'Added!' : 'Want this'}
                  actionLoading={
                    addToWishlistMutation.isPending &&
                    addToWishlistMutation.variables?.isbn === isbn
                  }
                />
              );
            })}
          </div>
          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
            disabled={isLoading}
          />
        </>
      )}
    </div>
  );
}
