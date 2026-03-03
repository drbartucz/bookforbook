import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { users as usersApi, institutions as institutionsApi } from '../services/api.js';
import LoadingSpinner from '../components/common/LoadingSpinner.jsx';
import ErrorMessage from '../components/common/ErrorMessage.jsx';
import ConditionBadge from '../components/common/ConditionBadge.jsx';
import { format } from 'date-fns';
import styles from './PublicProfile.module.css';

export default function PublicProfile() {
  const { id } = useParams();

  const { data: profile, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['publicProfile', id],
    queryFn: () => usersApi.getPublicProfile(id).then((r) => r.data),
  });

  const { data: ratingsData } = useQuery({
    queryKey: ['userRatings', id],
    queryFn: () => usersApi.getUserRatings(id, { page_size: 10 }).then((r) => r.data),
    enabled: !!profile,
  });

  const { data: wantedData } = useQuery({
    queryKey: ['institutionWanted', id],
    queryFn: () => institutionsApi.getWantedList(id, { page_size: 20 }).then((r) => r.data),
    enabled: !!profile && profile.account_type === 'institution',
  });

  if (isLoading) return <LoadingSpinner center size="lg" />;
  if (isError) return <ErrorMessage error={error} onRetry={refetch} />;
  if (!profile) return null;

  const ratings = ratingsData?.results ?? ratingsData ?? [];
  const wantedBooks = wantedData?.results ?? wantedData ?? [];
  const isInstitution = profile.account_type === 'institution';

  return (
    <div className={styles.page}>
      {/* Profile header */}
      <div className={`card ${styles.profileCard}`}>
        <div className={styles.avatar}>
          {profile.username?.[0]?.toUpperCase() ?? 'U'}
        </div>
        <div className={styles.profileInfo}>
          <div className={styles.nameRow}>
            <h1 className={styles.username}>@{profile.username}</h1>
            {isInstitution && (
              <span className="badge badge-blue">Institution</span>
            )}
            {profile.is_verified && (
              <span className="badge badge-green">Verified</span>
            )}
          </div>
          {profile.display_name && (
            <p className={styles.displayName}>{profile.display_name}</p>
          )}
          {profile.bio && (
            <p className={styles.bio}>{profile.bio}</p>
          )}
          {profile.location && (
            <p className={styles.location}>
              <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14">
                <path fillRule="evenodd" d="M9.69 18.933l.003.001C9.89 19.02 10 19 10 19s.11.02.308-.066l.002-.001.006-.003.018-.008a5.741 5.741 0 00.281-.14c.186-.096.446-.24.757-.433.62-.384 1.445-.966 2.274-1.765C15.302 14.988 17 12.493 17 9A7 7 0 103 9c0 3.492 1.698 5.988 3.355 7.584a13.731 13.731 0 002.273 1.765 11.842 11.842 0 00.976.544l.062.029.018.008.006.003zM10 11.25a2.25 2.25 0 100-4.5 2.25 2.25 0 000 4.5z" clipRule="evenodd" />
              </svg>
              {profile.location}
            </p>
          )}
        </div>

        {/* Stats */}
        <div className={styles.stats}>
          <div className={styles.stat}>
            <p className={styles.statValue}>{profile.total_trades ?? 0}</p>
            <p className={styles.statLabel}>Trades</p>
          </div>
          {profile.avg_recent_rating != null && (
            <div className={styles.stat}>
              <p className={styles.statValue}>
                {Number(profile.avg_recent_rating).toFixed(1)}
                <span className={styles.statStar}> ★</span>
              </p>
              <p className={styles.statLabel}>Avg Rating</p>
            </div>
          )}
          {profile.member_since && (
            <div className={styles.stat}>
              <p className={styles.statValue}>
                {format(new Date(profile.member_since), 'MMM yyyy')}
              </p>
              <p className={styles.statLabel}>Member since</p>
            </div>
          )}
        </div>
      </div>

      <div className={styles.content}>
        {/* Ratings */}
        <div className={`card ${styles.section}`}>
          <h2 className={styles.sectionTitle}>Recent Ratings</h2>
          {ratings.length === 0 ? (
            <p className={styles.emptyText}>No ratings yet.</p>
          ) : (
            <div className={styles.ratingList}>
              {ratings.map((rating, i) => (
                <div key={rating.id ?? i} className={styles.ratingItem}>
                  <div className={styles.ratingHeader}>
                    <div className={styles.ratingStars}>
                      {[1, 2, 3, 4, 5].map((star) => (
                        <span
                          key={star}
                          className={`${styles.ratingStar} ${rating.score >= star ? styles.ratingStarFilled : ''}`}
                        >
                          ★
                        </span>
                      ))}
                      <span className={styles.ratingScore}>{rating.score}/5</span>
                    </div>
                    <div className={styles.ratingMeta}>
                      {rating.rater && (
                        <Link to={`/profile/${rating.rater.id}`} className={styles.raterLink}>
                          @{rating.rater.username}
                        </Link>
                      )}
                      {rating.created_at && (
                        <span className={styles.ratingDate}>
                          {format(new Date(rating.created_at), 'MMM d, yyyy')}
                        </span>
                      )}
                    </div>
                  </div>
                  {rating.comment && (
                    <p className={styles.ratingComment}>{rating.comment}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Institution wanted books */}
        {isInstitution && (
          <div className={`card ${styles.section}`}>
            <h2 className={styles.sectionTitle}>Wanted Books</h2>
            <p className={styles.sectionSubtitle}>
              This institution is looking for these books as donations or trades.
            </p>
            {wantedBooks.length === 0 ? (
              <p className={styles.emptyText}>No wanted books listed.</p>
            ) : (
              <div className={styles.wantedGrid}>
                {wantedBooks.map((item, i) => {
                  const book = item.book ?? item;
                  return (
                    <div key={item.id ?? i} className={styles.wantedItem}>
                      {book.cover_url && (
                        <img src={book.cover_url} alt={book.title} className={styles.wantedCover} />
                      )}
                      <div className={styles.wantedInfo}>
                        <p className={styles.wantedTitle}>{book.title}</p>
                        {book.author && <p className={styles.wantedAuthor}>{book.author}</p>}
                        {item.min_condition && (
                          <span>
                            Min: <ConditionBadge condition={item.min_condition} />
                          </span>
                        )}
                        {item.quantity_needed && (
                          <p className={styles.wantedQty}>Need: {item.quantity_needed}</p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
