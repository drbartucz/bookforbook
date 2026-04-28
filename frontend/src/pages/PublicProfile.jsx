import React, { useEffect, useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { users as usersApi, institutions as institutionsApi, wishlist as wishlistApi } from '../services/api.js';
import useAuth from '../hooks/useAuth.js';
import LoadingSpinner from '../components/common/LoadingSpinner.jsx';
import ErrorMessage from '../components/common/ErrorMessage.jsx';
import ConditionBadge, { CONDITION_CONFIG } from '../components/common/ConditionBadge.jsx';
import Tooltip from '../components/common/Tooltip.jsx';
import { format } from 'date-fns';
import { getBookCoverUrl, getBookPrimaryAuthor } from '../utils/book.js';
import styles from './PublicProfile.module.css';

const DEFAULT_WISHLIST_PREFERENCES = {
  min_condition: 'any',
  edition_preference: 'same_language',
  allow_translations: false,
  exclude_abridged: true,
  format_preferences: [],
};

const EDITION_PREFERENCE_OPTIONS = [
  { value: 'exact', label: 'Exact edition only' },
  { value: 'same_language', label: 'Same work, same language' },
  { value: 'any_language', label: 'Same work, any language/translation' },
  { value: 'custom', label: 'Custom rules' },
];

const FORMAT_OPTIONS = [
  { value: 'hardcover', label: 'Hardcover' },
  { value: 'paperback', label: 'Paperback' },
  { value: 'mass_market', label: 'Mass Market' },
  { value: 'large_print', label: 'Large Print' },
  { value: 'audiobook', label: 'Audiobook' },
];

const CONDITION_OPTIONS = [
  { value: 'any', label: 'Any condition' },
  ...Object.entries(CONDITION_CONFIG).map(([value, cfg]) => ({ value, label: cfg.label })),
];

function getWishlistPreferenceStorageKey(userId) {
  return `wishlist-preferences:${userId}`;
}

function loadStoredWishlistPreferences(userId) {
  if (!userId) return DEFAULT_WISHLIST_PREFERENCES;
  try {
    const raw = localStorage.getItem(getWishlistPreferenceStorageKey(userId));
    if (!raw) return DEFAULT_WISHLIST_PREFERENCES;
    const parsed = JSON.parse(raw);
    return {
      ...DEFAULT_WISHLIST_PREFERENCES,
      ...parsed,
      format_preferences: Array.isArray(parsed?.format_preferences) ? parsed.format_preferences : [],
    };
  } catch {
    return DEFAULT_WISHLIST_PREFERENCES;
  }
}

function saveWishlistPreferences(userId, preferences) {
  if (!userId) return;
  try {
    localStorage.setItem(getWishlistPreferenceStorageKey(userId), JSON.stringify(preferences));
  } catch {
    // Ignore storage failures and continue with server updates.
  }
}

export default function PublicProfile() {
  const queryClient = useQueryClient();
  const { id } = useParams();
  const { user, isAuthenticated } = useAuth();
  const isOwnProfile = isAuthenticated && user?.id != null && String(user.id) === String(id);
  const [wishlistPreferences, setWishlistPreferences] = useState(DEFAULT_WISHLIST_PREFERENCES);
  const [wishlistPrefMessage, setWishlistPrefMessage] = useState(null);
  const [wishlistPrefError, setWishlistPrefError] = useState(null);

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

  const { data: offeredBooksData } = useQuery({
    queryKey: ['userOfferedBooks', id],
    queryFn: () => usersApi.getUserOfferedBooks(id).then((r) => r.data),
    enabled: !!profile,
  });

  const { data: publicWantedData } = useQuery({
    queryKey: ['userWantedBooks', id],
    queryFn: () => usersApi.getUserWantedBooks(id).then((r) => r.data),
    enabled: !!profile && profile.account_type !== 'institution',
  });

  const { data: meData } = useQuery({
    queryKey: ['me'],
    queryFn: () => usersApi.getMe().then((r) => r.data),
    enabled: isOwnProfile,
  });

  const { data: wishlistData } = useQuery({
    queryKey: ['profileWishlist', id],
    queryFn: () => wishlistApi.list({ page: 1, page_size: 100 }).then((r) => r.data),
    enabled: isOwnProfile,
  });

  const wishlistItems = useMemo(() => wishlistData?.results ?? [], [wishlistData]);

  useEffect(() => {
    if (!isOwnProfile) return;
    const stored = loadStoredWishlistPreferences(user?.id);
    if (wishlistItems.length > 0) {
      const first = wishlistItems[0];
      setWishlistPreferences({
        min_condition: first.min_condition ?? DEFAULT_WISHLIST_PREFERENCES.min_condition,
        edition_preference: first.edition_preference ?? DEFAULT_WISHLIST_PREFERENCES.edition_preference,
        allow_translations: Boolean(first.allow_translations),
        exclude_abridged: first.exclude_abridged !== false,
        format_preferences: Array.isArray(first.format_preferences) ? first.format_preferences : [],
      });
      return;
    }
    setWishlistPreferences(stored);
  }, [isOwnProfile, user?.id, wishlistItems]);

  const saveWishlistPreferencesMutation = useMutation({
    mutationFn: async (nextPreferences) => {
      saveWishlistPreferences(user?.id, nextPreferences);

      if (wishlistItems.length === 0) {
        return;
      }

      const payload = {
        min_condition:
          nextPreferences.min_condition === 'any' ? 'acceptable' : nextPreferences.min_condition,
        edition_preference: nextPreferences.edition_preference,
      };

      if (nextPreferences.edition_preference === 'custom') {
        payload.allow_translations = nextPreferences.allow_translations;
        payload.exclude_abridged = nextPreferences.exclude_abridged;
        payload.format_preferences = nextPreferences.format_preferences;
      }

      await Promise.all(
        wishlistItems.map((item) => wishlistApi.update(item.id, payload))
      );
    },
    onSuccess: async () => {
      setWishlistPrefError(null);
      setWishlistPrefMessage(
        wishlistItems.length > 0
          ? 'Wishlist match preferences updated for your current wishlist items.'
          : 'Wishlist match defaults saved. New wishlist items will use these defaults.'
      );
      await queryClient.invalidateQueries({ queryKey: ['profileWishlist', id] });
      await queryClient.invalidateQueries({ queryKey: ['wishlist'] });
    },
    onError: (mutationError) => {
      const detail = mutationError?.response?.data?.detail;
      setWishlistPrefError(
        typeof detail === 'string' ? detail : 'Could not save wishlist match preferences.'
      );
      setWishlistPrefMessage(null);
    },
  });

  if (isLoading) return <LoadingSpinner center size="lg" />;
  if (isError) return <ErrorMessage error={error} onRetry={refetch} />;
  if (!profile) return null;

  const ratings = ratingsData?.results ?? ratingsData ?? [];
  const wantedBooks = wantedData?.results ?? wantedData ?? [];
  const offeredBooks = offeredBooksData ?? [];
  const publicWantedBooks = publicWantedData ?? [];
  const isInstitution = profile.account_type === 'institution';
  const hasOwnAddress = Boolean(
    meData?.address_line_1 && meData?.city && meData?.state && meData?.zip_code
  );
  const ownAddressStatus = meData?.address_verification_status;

  function setPreferenceField(field, value) {
    setWishlistPrefMessage(null);
    setWishlistPrefError(null);
    setWishlistPreferences((current) => ({ ...current, [field]: value }));
  }

  function toggleFormatPreference(formatValue) {
    setWishlistPrefMessage(null);
    setWishlistPrefError(null);
    setWishlistPreferences((current) => {
      if (current.format_preferences.includes(formatValue)) {
        return {
          ...current,
          format_preferences: current.format_preferences.filter((value) => value !== formatValue),
        };
      }
      return {
        ...current,
        format_preferences: [...current.format_preferences, formatValue],
      };
    });
  }

  function handleWishlistPreferenceSubmit(event) {
    event.preventDefault();
    saveWishlistPreferencesMutation.mutate(wishlistPreferences);
  }

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
              <Tooltip content="This institution's identity has been confirmed by BookForBook.">
                <span className="badge badge-green">Verified</span>
              </Tooltip>
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
              <p className={styles.statLabel}>
                Avg Rating
                <Tooltip content="Average across their last 10 completed trades. See individual ratings below." />
              </p>
            </div>
          )}
          {profile.created_at && (
            <div className={styles.stat}>
              <p className={styles.statValue}>
                {format(new Date(profile.created_at), 'MMM yyyy')}
              </p>
              <p className={styles.statLabel}>Member since</p>
            </div>
          )}
        </div>
      </div>

      <div className={styles.content}>
        {isOwnProfile && (
          <div className={`card ${styles.section}`}>
            <div className={styles.addressHeader}>
              <h2 className={styles.sectionTitle}>Shipping Address</h2>
              <Link to="/account" className={styles.addressEditLink}>
                Edit address
              </Link>
            </div>

            {hasOwnAddress ? (
              <>
                <p className={styles.addressLine}>{meData.full_name}</p>
                <p className={styles.addressLine}>{meData.address_line_1}</p>
                {meData.address_line_2 && <p className={styles.addressLine}>{meData.address_line_2}</p>}
                <p className={styles.addressLine}>
                  {meData.city}, {meData.state} {meData.zip_code}
                </p>
                <p className={styles.addressMeta}>
                  Status:{' '}
                  <strong>
                    {ownAddressStatus === 'verified'
                      ? 'Verified'
                      : ownAddressStatus === 'failed'
                        ? 'Needs review'
                        : 'Not verified'}
                  </strong>
                </p>
              </>
            ) : (
              <>
                <p className={styles.emptyText}>No shipping address on file yet.</p>
                <Link to="/account" className="btn btn-primary btn-sm">
                  Add address
                </Link>
              </>
            )}
          </div>
        )}

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
                      {getBookCoverUrl(book) && (
                        <img src={getBookCoverUrl(book)} alt={book.title} className={styles.wantedCover} />
                      )}
                      <div className={styles.wantedInfo}>
                        <p className={styles.wantedTitle}>{book.title}</p>
                        {getBookPrimaryAuthor(book) && <p className={styles.wantedAuthor}>{getBookPrimaryAuthor(book)}</p>}
                        {(book.isbn_13 || book.isbn_10) && (
                          <p className={styles.wantedIsbn}>ISBN: {book.isbn_13 || book.isbn_10}</p>
                        )}
                        {item.min_condition && (
                          <span>
                            Min: <ConditionBadge condition={item.min_condition} />
                          </span>
                        )}
                        {item.quantity_needed && (
                          <Tooltip content={`This institution needs ${item.quantity_needed} more ${item.quantity_needed === 1 ? 'copy' : 'copies'} of this book.`}>
                            <p className={styles.wantedQty}>Need: {item.quantity_needed}</p>
                          </Tooltip>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Offered books (all users) */}
        <div className={`card ${styles.section}`}>
          <h2 className={styles.sectionTitle}>Offered Books</h2>
          <p className={styles.sectionSubtitle}>
            Books this user is currently offering for trade.
          </p>
          {offeredBooks.length === 0 ? (
            <p className={styles.emptyText}>No books offered yet.</p>
          ) : (
            <div className={styles.wantedGrid}>
              {offeredBooks.map((item, i) => {
                const book = item.book ?? item;
                return (
                  <div key={item.id ?? i} className={styles.wantedItem}>
                    {getBookCoverUrl(book) && (
                      <img src={getBookCoverUrl(book)} alt={book.title} className={styles.wantedCover} />
                    )}
                    <div className={styles.wantedInfo}>
                      <p className={styles.wantedTitle}>{book.title}</p>
                      {getBookPrimaryAuthor(book) && <p className={styles.wantedAuthor}>{getBookPrimaryAuthor(book)}</p>}
                      {(book.isbn_13 || book.isbn_10) && (
                        <p className={styles.wantedIsbn}>ISBN: {book.isbn_13 || book.isbn_10}</p>
                      )}
                      {item.condition && (
                        <span>
                          <ConditionBadge condition={item.condition} />
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Wanted books (non-institution users) */}
        {!isInstitution && (
          <div className={`card ${styles.section}`}>
            <h2 className={styles.sectionTitle}>Wanted Books</h2>
            <p className={styles.sectionSubtitle}>
              Books this user is looking to receive via trade.
            </p>
            {publicWantedBooks.length === 0 ? (
              <p className={styles.emptyText}>No wanted books listed.</p>
            ) : (
              <div className={styles.wantedGrid}>
                {publicWantedBooks.map((item, i) => {
                  const book = item.book ?? item;
                  return (
                    <div key={item.id ?? i} className={styles.wantedItem}>
                      {getBookCoverUrl(book) && (
                        <img src={getBookCoverUrl(book)} alt={book.title} className={styles.wantedCover} />
                      )}
                      <div className={styles.wantedInfo}>
                        <p className={styles.wantedTitle}>{book.title}</p>
                        {getBookPrimaryAuthor(book) && <p className={styles.wantedAuthor}>{getBookPrimaryAuthor(book)}</p>}
                        {(book.isbn_13 || book.isbn_10) && (
                          <p className={styles.wantedIsbn}>ISBN: {book.isbn_13 || book.isbn_10}</p>
                        )}
                        {item.min_condition && (
                          <span>
                            Min: <ConditionBadge condition={item.min_condition} />
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {isOwnProfile && (
          <div className={`card ${styles.section}`}>
            <div className={styles.addressHeader}>
              <h2 className={styles.sectionTitle}>Wishlist Match Preferences</h2>
              <span className={`${styles.preferenceScopeChip} ${wishlistItems.length > 0 ? styles.preferenceScopeChipApplied : styles.preferenceScopeChipDefaults}`}>
                {wishlistItems.length > 0
                  ? `Applied to ${wishlistItems.length} current item${wishlistItems.length === 1 ? '' : 's'}`
                  : 'Defaults for future items'}
              </span>
            </div>
            <p className={styles.sectionSubtitle}>
              Control how flexible matching should be for your wishlist. If you have no wishlist items yet, these will be saved as your defaults.
            </p>

            {wishlistPrefError && <div className="alert alert-error">{wishlistPrefError}</div>}
            {wishlistPrefMessage && <div className="alert alert-success">{wishlistPrefMessage}</div>}

            <form onSubmit={handleWishlistPreferenceSubmit} className={styles.preferencesForm}>
              <div className="form-group">
                <label className="form-label" htmlFor="wishlistMinCondition">Minimum acceptable condition</label>
                <select
                  id="wishlistMinCondition"
                  className="form-input"
                  value={wishlistPreferences.min_condition}
                  onChange={(event) => setPreferenceField('min_condition', event.target.value)}
                >
                  {CONDITION_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label" htmlFor="wishlistEditionPreference">Edition matching</label>
                <select
                  id="wishlistEditionPreference"
                  className="form-input"
                  value={wishlistPreferences.edition_preference}
                  onChange={(event) => setPreferenceField('edition_preference', event.target.value)}
                >
                  {EDITION_PREFERENCE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>

              {wishlistPreferences.edition_preference === 'custom' && (
                <div className={styles.customRulesBlock}>
                  <label className={styles.inlineCheckbox}>
                    <input
                      type="checkbox"
                      checked={wishlistPreferences.allow_translations}
                      onChange={(event) => setPreferenceField('allow_translations', event.target.checked)}
                    />
                    Include translations
                  </label>
                  <label className={styles.inlineCheckbox}>
                    <input
                      type="checkbox"
                      checked={wishlistPreferences.exclude_abridged}
                      onChange={(event) => setPreferenceField('exclude_abridged', event.target.checked)}
                    />
                    Exclude abridged versions
                  </label>

                  <div>
                    <p className={styles.formLabel}>Allowed formats</p>
                    <div className={styles.formatButtonRow}>
                      {FORMAT_OPTIONS.map((format) => {
                        const active = wishlistPreferences.format_preferences.includes(format.value);
                        return (
                          <button
                            key={format.value}
                            type="button"
                            className={`btn btn-sm ${active ? 'btn-primary' : 'btn-secondary'}`}
                            onClick={() => toggleFormatPreference(format.value)}
                          >
                            {format.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              <div className={styles.actionsRow}>
                <button type="submit" className="btn btn-primary" disabled={saveWishlistPreferencesMutation.isPending}>
                  {saveWishlistPreferencesMutation.isPending ? 'Saving...' : 'Save wishlist preferences'}
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
