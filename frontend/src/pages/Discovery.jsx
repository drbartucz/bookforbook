import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { matches as matchesApi, wishlist as wishlistApi } from '../services/api.js';
import LoadingSpinner from '../components/common/LoadingSpinner.jsx';
import ErrorMessage from '../components/common/ErrorMessage.jsx';
import BookCard from '../components/common/BookCard.jsx';
import { getBookIsbn } from '../utils/book.js';
import styles from './Discovery.module.css';

export default function Discovery() {
  const queryClient = useQueryClient();
  const [addedToWishlist, setAddedToWishlist] = useState(new Set());

  const { data: partners, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['discovery-partners'],
    queryFn: () => matchesApi.reverseDiscovery().then((r) => r.data),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });

  const addToWishlistMutation = useMutation({
    mutationFn: ({ isbn }) => wishlistApi.add({ isbn }),
    onSuccess: (_, variables) => {
      setAddedToWishlist((prev) => new Set([...prev, variables.isbn]));
      queryClient.invalidateQueries({ queryKey: ['wishlist'] });
      // Optionally refetch discovery to remove books already in wishlist
      queryClient.invalidateQueries({ queryKey: ['discovery-partners'] });
    },
  });

  if (isLoading) return <LoadingSpinner center size="lg" label="Finding potential trade partners..." />;
  if (isError) return <ErrorMessage error={error} onRetry={refetch} />;

  return (
    <div className={styles.container}>
      <div className="page-header">
        <h1 className="page-title">Match Discovery</h1>
        <p className="page-subtitle">
          These users want books you have available. Browse their collections to find something you want in return!
        </p>
      </div>

      {partners.length === 0 ? (
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>No potential partners found yet</p>
          <p className={styles.emptySubtitle}>
            Discovery works better as you add more books to your have-list. 
            When someone wants one of your books, they'll show up here.
          </p>
          <Link to="/my-books" className="btn btn-primary" style={{ marginTop: '1.5rem' }}>
            Manage my books
          </Link>
        </div>
      ) : (
        <div className={styles.partnerList}>
          {partners.map((partner) => (
            <div key={partner.user.id} className={`card ${styles.partnerCard}`}>
              <div className={styles.partnerHeader}>
                <div className={styles.partnerInfo}>
                  <Link to={`/profile/${partner.user.id}`} className={styles.partnerName}>
                    @{partner.user.username}
                  </Link>
                  {partner.user.avg_recent_rating && (
                    <span className={styles.partnerRating}>
                      &bull; {Number(partner.user.avg_recent_rating).toFixed(1)} ★
                    </span>
                  )}
                </div>
                <div className={styles.wantsSection}>
                  <span className={styles.wantsLabel}>Wants from you:</span>
                  <div className={styles.wantsList}>
                    {partner.they_want.map((ub) => (
                      <span key={ub.id} className={`badge badge-blue ${styles.wantBadge}`}>
                        {ub.book.title}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className={styles.offersSection}>
                <h3 className={styles.offersTitle}>Books they offer:</h3>
                <div className={styles.offersGrid}>
                  {partner.they_offer.map((ub) => {
                    const isbn = getBookIsbn(ub.book);
                    const alreadyAdded = isbn && addedToWishlist.has(isbn);

                    return (
                      <div key={ub.id} className={styles.bookWrapper}>
                        <BookCard
                          book={ub.book}
                          onAction={
                            !alreadyAdded
                              ? () => addToWishlistMutation.mutate({ isbn })
                              : undefined
                          }
                          actionLabel={alreadyAdded ? 'Added!' : 'I want this'}
                          actionTooltip="Adds this book to your wishlist. If you both want each other's books, a match will be created automatically."
                          actionLoading={
                            addToWishlistMutation.isPending &&
                            addToWishlistMutation.variables?.isbn === isbn
                          }
                        />
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
