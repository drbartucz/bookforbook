import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { myBooks as myBooksApi } from '../services/api.js';
import LoadingSpinner from '../components/common/LoadingSpinner.jsx';
import ErrorMessage from '../components/common/ErrorMessage.jsx';
import ConditionBadge, { CONDITION_CONFIG } from '../components/common/ConditionBadge.jsx';
import ISBNInput from '../components/common/ISBNInput.jsx';
import Pagination from '../components/common/Pagination.jsx';
import AddressPromptModal from '../components/common/AddressPromptModal.jsx';
import { getBookCoverUrl, getBookPrimaryAuthor } from '../utils/book.js';
import styles from './MyBooks.module.css';

const PAGE_SIZE = 20;

const CONDITION_OPTIONS = Object.entries(CONDITION_CONFIG).map(([value, { label }]) => ({
  value,
  label,
}));

const STATUS_CONFIG = {
  available: { label: 'Available', cls: 'badge-green' },
  in_trade: { label: 'In Trade', cls: 'badge-amber' },
  reserved: { label: 'Reserved', cls: 'badge-blue' },
};

// Helper function to normalize bibliographic format for display.
function getFormatLabel(formatValue) {
  return formatValue?.trim() || 'Not listed';
}

// Helper to format date
function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function MyBooks() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [showAddForm, setShowAddForm] = useState(false);
  const [isbn, setIsbn] = useState('');
  const [foundBook, setFoundBook] = useState(null);
  const [addCondition, setAddCondition] = useState('good');
  const [addError, setAddError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editCondition, setEditCondition] = useState('');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [showAddressPrompt, setShowAddressPrompt] = useState(false);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['myBooks', page, sortBy, sortOrder],
    queryFn: () => myBooksApi.list({ page, page_size: PAGE_SIZE, sort_by: sortBy, sort_order: sortOrder }).then((r) => r.data),
  });

  const addMutation = useMutation({
    mutationFn: (bookData) => myBooksApi.add(bookData),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['myBooks'] });
      setShowAddForm(false);
      setIsbn('');
      setFoundBook(null);
      setAddCondition('good');
      setAddError(null);
      if (response?.headers?.['x-address-prompt'] === 'add_now') {
        setShowAddressPrompt(true);
      }
    },
    onError: (err) => {
      const msg =
        err?.response?.data?.detail ||
        err?.response?.data?.non_field_errors?.join(' ') ||
        'Failed to add book. Please try again.';
      setAddError(msg);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => myBooksApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myBooks'] });
      setEditingId(null);
    },
  });

  const removeMutation = useMutation({
    mutationFn: (id) => myBooksApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['myBooks'] });
    },
  });

  const books = data?.results ?? [];
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

    // Count existing copies of this book across all cached pages
    const targetIsbn = foundBook.isbn_13 || foundBook.isbn_10;
    let existingCount = 0;
    for (const [, pageData] of queryClient.getQueriesData({ queryKey: ['myBooks'] })) {
      if (!pageData?.results) continue;
      for (const item of pageData.results) {
        const itemIsbn = item.book?.isbn_13 || item.book?.isbn_10;
        if (itemIsbn && targetIsbn && itemIsbn === targetIsbn) existingCount++;
      }
    }

    if (existingCount > 0) {
      const title = foundBook.title || 'this book';
      const copyWord = existingCount === 1 ? 'copy' : 'copies';
      if (!window.confirm(`You already have ${existingCount} ${copyWord} of "${title}" listed. Would you like to add another?`)) {
        return;
      }
    }

    addMutation.mutate({
      isbn: isbn.trim().replace(/[\s-]/g, ''),
      condition: addCondition,
    });
  }

  function handleRemove(id) {
    if (window.confirm('Remove this book from your have-list?')) {
      removeMutation.mutate(id);
    }
  }

  function startEdit(item) {
    setEditingId(item.id);
    setEditCondition(item.condition);
  }

  function saveEdit(id) {
    updateMutation.mutate({ id, data: { condition: editCondition } });
  }

  return (
    <div>
      <div className={styles.header}>
        <div>
          <h1 className="page-title">My Books</h1>
          <p className="page-subtitle">Books you have and are willing to trade.</p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => setShowAddForm((v) => !v)}
        >
          {showAddForm ? 'Cancel' : '+ Add Book'}
        </button>
      </div>

      {/* Add book form */}
      {showAddForm && (
        <form className={`card ${styles.addForm}`} onSubmit={handleAddSubmit}>
          <h2 className={styles.formTitle}>Add a Book</h2>

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
            <label className="form-label" htmlFor="addCondition">
              Condition
            </label>
            <select
              id="addCondition"
              className="form-input"
              value={addCondition}
              onChange={(e) => setAddCondition(e.target.value)}
            >
              {CONDITION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={addMutation.isPending || !foundBook}
          >
            {addMutation.isPending ? 'Adding...' : 'Add to My Books'}
          </button>
        </form>
      )}

      {/* Book list */}
      {isLoading ? (
        <LoadingSpinner center size="lg" />
      ) : isError ? (
        <ErrorMessage error={error} onRetry={refetch} />
      ) : books.length === 0 ? (
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

          <p className={styles.emptyTitle}>No books yet</p>
          <p className={styles.emptySubtitle}>
            Add books you own and want to trade. Use the ISBN lookup to find them quickly.
          </p>
          {!showAddForm && (
            <button
              className="btn btn-primary"
              style={{ marginTop: '1rem' }}
              onClick={() => setShowAddForm(true)}
            >
              Add your first book
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
          <div className={styles.bookList}>
            {books.map((item) => {
              const book = item.book ?? item;
              const isEditing = editingId === item.id;
              const statusConfig = STATUS_CONFIG[item.status] ?? { label: item.status, cls: 'badge-gray' };

              return (
                <div key={item.id} className={`card ${styles.bookItem}`}>
                  {getBookCoverUrl(book) && (
                    <img
                      src={getBookCoverUrl(book)}
                      alt={book.title}
                      className={styles.bookCover}
                    />
                  )}
                  <div className={styles.bookInfo}>
                    <p className={styles.bookTitle}>{book.title}</p>
                    <p className={styles.bookAuthor}>{getBookPrimaryAuthor(book) ?? 'Unknown Author'}</p>
                    <div className={styles.bookDetails}>
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
                    <div className={styles.bookMeta}>
                      <ConditionBadge condition={item.condition} />
                      <span className={`badge ${statusConfig.cls}`}>{statusConfig.label}</span>
                    </div>
                  </div>
                  <div className={styles.bookActions}>
                    {isEditing ? (
                      <div className={styles.editForm}>
                        <select
                          className="form-input"
                          value={editCondition}
                          onChange={(e) => setEditCondition(e.target.value)}
                          style={{ fontSize: '0.8125rem', padding: '0.375rem 0.625rem' }}
                        >
                          {CONDITION_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => saveEdit(item.id)}
                            disabled={updateMutation.isPending}
                          >
                            Save
                          </button>
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => setEditingId(null)}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => startEdit(item)}
                          disabled={item.status === 'in_trade'}
                        >
                          Edit
                        </button>
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => handleRemove(item.id)}
                          disabled={removeMutation.isPending || item.status === 'in_trade'}
                        >
                          Remove
                        </button>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </>
      )}

      <AddressPromptModal open={showAddressPrompt} onClose={() => setShowAddressPrompt(false)} />
    </div>
  );
}
