import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { wishlist as wishlistApi } from '../services/api.js';
import LoadingSpinner from '../components/common/LoadingSpinner.jsx';
import ErrorMessage from '../components/common/ErrorMessage.jsx';
import ConditionBadge, { CONDITION_CONFIG } from '../components/common/ConditionBadge.jsx';
import ISBNInput from '../components/common/ISBNInput.jsx';
import Pagination from '../components/common/Pagination.jsx';
import { getBookCoverUrl, getBookPrimaryAuthor } from '../utils/book.js';
import styles from './Wishlist.module.css';

const PAGE_SIZE = 20;

// Helper function to normalize bibliographic format for display.
function getFormatLabel(formatValue) {
  return formatValue?.trim() || 'Unknown';
}

// Helper to format date
function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

const CONDITION_OPTIONS = [
  { value: 'any', label: 'Any condition' },
  ...Object.entries(CONDITION_CONFIG).map(([value, { label }]) => ({ value, label })),
];

export default function Wishlist() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [showAddForm, setShowAddForm] = useState(false);
  const [isbn, setIsbn] = useState('');
  const [foundBook, setFoundBook] = useState(null);
  const [minCondition, setMinCondition] = useState('any');
  const [addError, setAddError] = useState(null);
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['wishlist', page, sortBy, sortOrder],
    queryFn: () => wishlistApi.list({ page, page_size: PAGE_SIZE, sort_by: sortBy, sort_order: sortOrder }).then((r) => r.data),
  });

  const addMutation = useMutation({
    mutationFn: (itemData) => wishlistApi.add(itemData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wishlist'] });
      setShowAddForm(false);
      setIsbn('');
      setFoundBook(null);
      setMinCondition('any');
      setAddError(null);
    },
    onError: (err) => {
      const msg =
        err?.response?.data?.detail ||
        err?.response?.data?.non_field_errors?.join(' ') ||
        'Failed to add to wishlist.';
      setAddError(msg);
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }) => wishlistApi.update(id, { is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['wishlist'] }),
  });

  const removeMutation = useMutation({
    mutationFn: (id) => wishlistApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['wishlist'] }),
  });

  const items = data?.results ?? [];
  const totalPages = Math.ceil((data?.count ?? 0) / PAGE_SIZE);

  function handleAddSubmit(e) {
    e.preventDefault();
    if (!isbn.trim()) {
      setAddError('Please enter an ISBN.');
      return;
    }
    if (!foundBook) {
      setAddError('Please look up the ISBN first.');
      return;
    }
    setAddError(null);
    const payload = { isbn: isbn.trim().replace(/-/g, '') };
    if (minCondition && minCondition !== 'any') {
      payload.min_condition = minCondition;
    }
    addMutation.mutate(payload);
  }

  function handleRemove(id) {
    if (window.confirm('Remove this book from your wishlist?')) {
      removeMutation.mutate(id);
    }
  }

  return (
    <div>
      <div className={styles.header}>
        <div>
          <h1 className="page-title">My Wishlist</h1>
          <p className="page-subtitle">Books you want to receive in a trade.</p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => setShowAddForm((v) => !v)}
        >
          {showAddForm ? 'Cancel' : '+ Add to Wishlist'}
        </button>
      </div>

      {/* Add form */}
      {showAddForm && (
        <form className={`card ${styles.addForm}`} onSubmit={handleAddSubmit}>
          <h2 className={styles.formTitle}>Add to Wishlist</h2>

          {addError && <div className="alert alert-error">{addError}</div>}

          <div className="form-group">
            <label className="form-label">ISBN</label>
            <ISBNInput
              value={isbn}
              onChange={setIsbn}
              onBookFound={setFoundBook}
              foundBook={foundBook}
            />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="minCondition">
              Minimum acceptable condition
            </label>
            <select
              id="minCondition"
              className="form-input"
              value={minCondition}
              onChange={(e) => setMinCondition(e.target.value)}
            >
              {CONDITION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <p className="form-hint">
              You&apos;ll only be matched with books meeting this condition or better.
            </p>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={addMutation.isPending || !foundBook}
          >
            {addMutation.isPending ? 'Adding...' : 'Add to Wishlist'}
          </button>
        </form>
      )}

      {/* List */}
      {isLoading ? (
        <LoadingSpinner center size="lg" />
      ) : isError ? (
        <ErrorMessage error={error} onRetry={refetch} />
      ) : items.length === 0 ? (
        <div className={styles.empty}>
          <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: '150px' }}>
              <label className="form-label">Sort by</label>
              <select
                className="form-input"
                value={sortBy}
                onChange={(e) => {
                  setSortBy(e.target.value);
                  setPage(1);
                }}
              >
                <option value="created_at">Date Added</option>
                <option value="title">Title</option>
                <option value="author">Author</option>
              </select>
            </div>
            <div style={{ flex: 1, minWidth: '150px' }}>
              <label className="form-label">Order</label>
              <select
                className="form-input"
                value={sortOrder}
                onChange={(e) => {
                  setSortOrder(e.target.value);
                  setPage(1);
                }}
              >
                <option value="desc">Descending</option>
                <option value="asc">Ascending</option>
              </select>
            </div>
          </div>
          <p className={styles.emptyTitle}>Your wishlist is empty</p>
          <p className={styles.emptySubtitle}>
            Add books you want to receive. When someone in your area has one to trade, you&apos;ll be matched automatically.
          </p>
          {!showAddForm && (
            <button
              className="btn btn-primary"
              style={{ marginTop: '1rem' }}
              onClick={() => setShowAddForm(true)}
            >
              Add your first wish
            </button>
          )}
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: '150px' }}>
              <label className="form-label">Sort by</label>
              <select
                className="form-input"
                value={sortBy}
                onChange={(e) => {
                  setSortBy(e.target.value);
                  setPage(1);
                }}
              >
                <option value="created_at">Date Added</option>
                <option value="title">Title</option>
                <option value="author">Author</option>
              </select>
            </div>
            <div style={{ flex: 1, minWidth: '150px' }}>
              <label className="form-label">Order</label>
              <select
                className="form-input"
                value={sortOrder}
                onChange={(e) => {
                  setSortOrder(e.target.value);
                  setPage(1);
                }}
              >
                <option value="desc">Descending</option>
                <option value="asc">Ascending</option>
              </select>
            </div>
          </div>
          <div className={styles.wishlistGrid}>
            {items.map((item) => {
              const book = item.book ?? item;
              return (
                <div key={item.id} className={`card ${styles.wishItem} ${!item.is_active ? styles.inactive : ''}`}>
                  {getBookCoverUrl(book) && (
                    <img src={getBookCoverUrl(book)} alt={book.title} className={styles.cover} />
                  )}
                  <div className={styles.info}>
                    <p className={styles.title}>{book.title}</p>
                    <p className={styles.author}>{getBookPrimaryAuthor(book) ?? 'Unknown Author'}</p>
                    <div className={styles.details}>
                      <span className={styles.detailItem}>
                        <strong>Format:</strong> {getFormatLabel(book.physical_format)}
                      </span>
                      <span className={styles.detailItem}>
                        <strong>ISBN:</strong> {book.isbn_13}
                      </span>
                      <span className={styles.detailItem}>
                        <strong>Added:</strong> {formatDate(item.created_at)}
                      </span>
                    </div>
                    <div className={styles.meta}>
                      {item.min_condition && item.min_condition !== 'any' ? (
                        <span className="text-sm text-gray">
                          Min: <ConditionBadge condition={item.min_condition} />
                        </span>
                      ) : (
                        <span className="badge badge-gray">Any condition</span>
                      )}
                      <span className={`badge ${item.is_active ? 'badge-green' : 'badge-gray'}`}>
                        {item.is_active ? 'Active' : 'Paused'}
                      </span>
                    </div>
                  </div>
                  <div className={styles.actions}>
                    <button
                      className={`btn btn-sm ${item.is_active ? 'btn-secondary' : 'btn-success'}`}
                      onClick={() => toggleMutation.mutate({ id: item.id, is_active: !item.is_active })}
                      disabled={toggleMutation.isPending}
                    >
                      {item.is_active ? 'Pause' : 'Resume'}
                    </button>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => handleRemove(item.id)}
                      disabled={removeMutation.isPending}
                    >
                      Remove
                    </button>
                  </div>
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
