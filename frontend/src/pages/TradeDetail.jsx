import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { trades as tradesApi } from '../services/api.js';
import useAuth from '../hooks/useAuth.js';
import LoadingSpinner from '../components/common/LoadingSpinner.jsx';
import ErrorMessage from '../components/common/ErrorMessage.jsx';
import ConditionBadge from '../components/common/ConditionBadge.jsx';
import { format } from 'date-fns';
import { getBookCoverUrl, getBookPrimaryAuthor } from '../utils/book.js';
import { buildTradeRatingPayload, mapTradeForView } from '../adapters/trades.js';
import styles from './TradeDetail.module.css';

const MESSAGE_MAX_LENGTH = 1000;

const MESSAGE_TYPES = [
  { value: 'general', label: 'General' },
  { value: 'shipping_update', label: 'Shipping Update' },
  { value: 'question', label: 'Question' },
  { value: 'issue', label: 'Issue' },
];

const TRADE_STATUS_CONFIG = {
  confirmed: { label: 'Confirmed — waiting to ship', cls: 'badge-blue' },
  shipping: { label: 'Books in transit', cls: 'badge-amber' },
  one_received: { label: 'One side received', cls: 'badge-amber' },
  completed: { label: 'Completed', cls: 'badge-green' },
  disputed: { label: 'Disputed', cls: 'badge-red' },
  cancelled: { label: 'Cancelled', cls: 'badge-gray' },
};

export default function TradeDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [msgType, setMsgType] = useState('general');
  const [msgContent, setMsgContent] = useState('');
  const [trackingNumber, setTrackingNumber] = useState('');
  const [showShipForm, setShowShipForm] = useState(false);
  const [showRateForm, setShowRateForm] = useState(false);
  const [ratingScore, setRatingScore] = useState(5);
  const [ratingComment, setRatingComment] = useState('');
  const [bookConditionAccurate, setBookConditionAccurate] = useState(true);
  const [actionError, setActionError] = useState(null);

  const {
    data: trade,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['trade', id],
    queryFn: () => tradesApi.getDetail(id).then((r) => r.data),
    refetchInterval: () => (document.hidden ? false : 30_000),
  });

  const {
    data: messagesData,
    isLoading: messagesLoading,
    refetch: refetchMessages,
  } = useQuery({
    queryKey: ['trade-messages', id],
    queryFn: () => tradesApi.getMessages(id).then((r) => r.data),
    refetchInterval: () => (document.hidden ? false : 30_000),
  });

  const sendMessageMutation = useMutation({
    mutationFn: (data) => tradesApi.sendMessage(id, data),
    onSuccess: () => {
      setMsgContent('');
      queryClient.invalidateQueries({ queryKey: ['trade-messages', id] });
      setActionError(null);
    },
    onError: (err) => setActionError(err?.response?.data?.detail || 'Failed to send message.'),
  });

  const markShippedMutation = useMutation({
    mutationFn: () => tradesApi.markShipped(id, { tracking_number: trackingNumber }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trade', id] });
      setShowShipForm(false);
      setTrackingNumber('');
      setActionError(null);
    },
    onError: (err) => setActionError(err?.response?.data?.detail || 'Failed to mark as shipped.'),
  });

  const markReceivedMutation = useMutation({
    mutationFn: () => tradesApi.markReceived(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trade', id] });
      setActionError(null);
    },
    onError: (err) => setActionError(err?.response?.data?.detail || 'Failed to mark as received.'),
  });

  const rateMutation = useMutation({
    mutationFn: () => {
      const payload = buildTradeRatingPayload(
        tradeView,
        {
          score: ratingScore,
          comment: ratingComment,
          bookConditionAccurate,
        }
      );

      if (!payload) {
        throw new Error('Unable to determine trade partner for rating.');
      }

      return tradesApi.rate(id, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trade', id] });
      setShowRateForm(false);
      setActionError(null);
    },
    onError: (err) => setActionError(err?.response?.data?.detail || 'Failed to submit rating.'),
  });

  if (isLoading) return <LoadingSpinner center size="lg" label="Loading trade details..." />;
  if (isError) return <ErrorMessage error={error} onRetry={refetch} />;
  if (!trade) return null;

  const tradeView = mapTradeForView(trade, user?.id);

  const statusConfig = TRADE_STATUS_CONFIG[tradeView.status] ?? { label: tradeView.status, cls: 'badge-gray' };

  const myBook = tradeView.myBook;
  const theirBook = tradeView.theirBook;
  const partner = tradeView.partner;

  const myBookData = myBook?.book;
  const theirBookData = theirBook?.book;

  const messages = messagesData?.results ?? messagesData ?? [];

  const isCompleted = tradeView.status === 'completed';
  const canMarkShipped = ['confirmed', 'one_received'].includes(tradeView.status) && !tradeView.myShipped;
  const canMarkReceived = ['shipping', 'one_received'].includes(tradeView.status) && tradeView.theyShipped && !tradeView.iReceived;
  const canRate = isCompleted && !tradeView.iRated;
  const messageLength = msgContent.length;

  function submitMessageIfValid() {
    const trimmed = msgContent.trim();
    if (!trimmed) {
      return;
    }
    if (trimmed.length > MESSAGE_MAX_LENGTH) {
      setActionError(`Message must be ${MESSAGE_MAX_LENGTH} characters or fewer.`);
      return;
    }
    sendMessageMutation.mutate({ content: trimmed, message_type: msgType });
  }

  return (
    <div>
      {/* Back link */}
      <Link to="/trades" className={styles.backLink}>
        &larr; Back to Trades
      </Link>

      <div className={styles.layout}>
        {/* Left: Trade details */}
        <div className={styles.main}>
          {/* Header */}
          <div className={`card ${styles.section}`}>
            <div className={styles.tradeTitle}>
              <div>
                <h1 className="page-title" style={{ marginBottom: '0.25rem' }}>
                  Trade #{trade.id}
                </h1>
                <span className={`badge ${statusConfig.cls}`}>{statusConfig.label}</span>
              </div>
              {trade.created_at && (
                <p className={styles.tradeDate}>
                  Started {format(new Date(trade.created_at), 'MMMM d, yyyy')}
                </p>
              )}
            </div>
          </div>

          {/* Book exchange summary */}
          <div className={`card ${styles.section}`}>
            <h2 className={styles.sectionTitle}>Book Exchange</h2>
            <div className={styles.exchangeGrid}>
              <BookSummary
                label="You send"
                book={myBookData}
                condition={myBook?.condition}
                shipped={tradeView.myShipped}
                shippedAt={tradeView.myShippedAt}
                trackingNumber={tradeView.myTracking}
                received={tradeView.theyReceived}
              />
              <div className={styles.exchangeIcon}>&#8646;</div>
              <BookSummary
                label="You receive"
                book={theirBookData}
                condition={theirBook?.condition}
                shipped={tradeView.theyShipped}
                shippedAt={tradeView.theyShippedAt}
                trackingNumber={tradeView.theirTracking}
                received={tradeView.iReceived}
              />
            </div>
          </div>

          {/* Shipping address */}
          {(tradeView.status !== 'confirmed') && (
            <div className={`card ${styles.section}`}>
              <h2 className={styles.sectionTitle}>Shipping Address</h2>
              {tradeView.partnerAddress ? (
                <div className={styles.address}>
                  <p>{tradeView.partnerAddress.name}</p>
                  <p>{tradeView.partnerAddress.street}</p>
                  {tradeView.partnerAddress.street2 && <p>{tradeView.partnerAddress.street2}</p>}
                  <p>
                    {tradeView.partnerAddress.city}, {tradeView.partnerAddress.state}{' '}
                    {tradeView.partnerAddress.zip}
                  </p>
                </div>
              ) : (
                <p className={styles.addressHidden}>
                  Address will be revealed when both parties confirm shipping.
                </p>
              )}
            </div>
          )}

          {/* Actions */}
          {actionError && (
            <div className="alert alert-error">{actionError}</div>
          )}

          <div className={styles.actions}>
            {canMarkShipped && (
              <>
                {showShipForm ? (
                  <div className={`card ${styles.section}`}>
                    <h2 className={styles.sectionTitle}>Mark as Shipped</h2>
                    <div className="form-group">
                      <label className="form-label" htmlFor="tracking">
                        Tracking number (optional)
                      </label>
                      <input
                        id="tracking"
                        type="text"
                        className="form-input"
                        value={trackingNumber}
                        onChange={(e) => setTrackingNumber(e.target.value)}
                        placeholder="e.g. 1Z999AA10123456784"
                      />
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
                      <button
                        className="btn btn-success"
                        onClick={() => markShippedMutation.mutate()}
                        disabled={markShippedMutation.isPending}
                      >
                        {markShippedMutation.isPending ? 'Marking...' : 'Confirm Shipped'}
                      </button>
                      <button
                        className="btn btn-secondary"
                        onClick={() => setShowShipForm(false)}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <button className="btn btn-primary" onClick={() => setShowShipForm(true)}>
                    Mark My Book as Shipped
                  </button>
                )}
              </>
            )}

            {canMarkReceived && (
              <button
                className="btn btn-success"
                onClick={() => {
                  if (window.confirm('Confirm you received the book?')) {
                    markReceivedMutation.mutate();
                  }
                }}
                disabled={markReceivedMutation.isPending}
              >
                {markReceivedMutation.isPending ? 'Marking...' : 'Mark Book Received'}
              </button>
            )}

            {canRate && (
              <>
                {showRateForm ? (
                  <div className={`card ${styles.section}`}>
                    <h2 className={styles.sectionTitle}>
                      Rate @{partner?.username ?? 'your trade partner'}
                    </h2>
                    <div className="form-group">
                      <label className="form-label">Rating</label>
                      <div className={styles.ratingRow}>
                        {[1, 2, 3, 4, 5].map((star) => (
                          <button
                            key={star}
                            type="button"
                            className={`${styles.star} ${ratingScore >= star ? styles.starActive : ''}`}
                            onClick={() => setRatingScore(star)}
                          >
                            ★
                          </button>
                        ))}
                        <span className={styles.ratingLabel}>{ratingScore} / 5</span>
                      </div>
                    </div>
                    <div className="form-group">
                      <label className="form-label" htmlFor="ratingComment">
                        Comment (optional)
                      </label>
                      <textarea
                        id="ratingComment"
                        className="form-input"
                        value={ratingComment}
                        onChange={(e) => setRatingComment(e.target.value)}
                        rows={3}
                        placeholder="How was the trade?"
                      />
                    </div>
                    <label className={styles.ratingCheckbox}>
                      <input
                        type="checkbox"
                        checked={bookConditionAccurate}
                        onChange={(e) => setBookConditionAccurate(e.target.checked)}
                      />
                      The book condition matched the listing.
                    </label>
                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
                      <button
                        className="btn btn-primary"
                        onClick={() => rateMutation.mutate()}
                        disabled={rateMutation.isPending}
                      >
                        {rateMutation.isPending ? 'Submitting...' : 'Submit Rating'}
                      </button>
                      <button className="btn btn-secondary" onClick={() => setShowRateForm(false)}>
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <button className="btn btn-warning" onClick={() => setShowRateForm(true)}>
                    Rate Trade Partner
                  </button>
                )}
              </>
            )}

            {tradeView.iRated && (
              <div className="alert alert-success">You have rated this trade. Thank you!</div>
            )}
          </div>
        </div>

        {/* Right: Messages */}
        <div className={styles.sidebar}>
          <div className={`card ${styles.messagesCard}`}>
            <div className={styles.messagesHeader}>
              <h2 className={styles.sectionTitle} style={{ margin: 0 }}>Messages</h2>
              <button
                className={styles.refreshBtn}
                onClick={refetchMessages}
                aria-label="Refresh messages"
              >
                &#8635;
              </button>
            </div>

            {messagesLoading ? (
              <LoadingSpinner center size="sm" />
            ) : (
              <div className={styles.messageThread}>
                {messages.length === 0 ? (
                  <p className={styles.noMessages}>No messages yet. Start the conversation!</p>
                ) : (
                  messages.map((msg, i) => {
                    const isMe = msg.sender?.id === user?.id || msg.is_mine;
                    return (
                      <div
                        key={msg.id ?? i}
                        className={`${styles.message} ${isMe ? styles.myMessage : styles.theirMessage}`}
                      >
                        <div className={styles.messageMeta}>
                          <span className={styles.messageSender}>
                            {isMe ? 'You' : (msg.sender?.username ?? 'Partner')}
                          </span>
                          {msg.message_type && msg.message_type !== 'general' && (
                            <span className={`badge badge-gray ${styles.msgType}`}>
                              {msg.message_type.replace('_', ' ')}
                            </span>
                          )}
                          {msg.created_at && (
                            <span className={styles.messageTime}>
                              {format(new Date(msg.created_at), 'MMM d, HH:mm')}
                            </span>
                          )}
                        </div>
                        <p className={styles.messageContent}>{msg.content}</p>
                      </div>
                    );
                  })
                )}
              </div>
            )}

            {/* Send message form */}
            <div className={styles.sendForm}>
              <div className="form-group">
                <select
                  className="form-input"
                  value={msgType}
                  onChange={(e) => setMsgType(e.target.value)}
                  style={{ fontSize: '0.8125rem' }}
                >
                  {MESSAGE_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className={styles.sendRow}>
                <textarea
                  className={`form-input ${styles.sendTextarea}`}
                  value={msgContent}
                  onChange={(e) => setMsgContent(e.target.value)}
                  placeholder="Type a message..."
                  rows={2}
                  maxLength={MESSAGE_MAX_LENGTH}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      submitMessageIfValid();
                    }
                  }}
                />
                <div className={styles.characterCount}>
                  {messageLength}/{MESSAGE_MAX_LENGTH}
                </div>
                <button
                  className="btn btn-primary"
                  onClick={submitMessageIfValid}
                  disabled={sendMessageMutation.isPending || !msgContent.trim()}
                  aria-label="Send message"
                >
                  {sendMessageMutation.isPending ? '...' : 'Send'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function BookSummary({ label, book, condition, shipped, shippedAt, trackingNumber, received }) {
  return (
    <div className={styles.bookSummary}>
      <p className={styles.bookSummaryLabel}>{label}</p>
      {book ? (
        <>
          {getBookCoverUrl(book) && (
            <img src={getBookCoverUrl(book)} alt={book.title} className={styles.bookSummaryCover} />
          )}
          <p className={styles.bookSummaryTitle}>{book.title}</p>
          {getBookPrimaryAuthor(book) && <p className={styles.bookSummaryAuthor}>{getBookPrimaryAuthor(book)}</p>}
          {condition && <ConditionBadge condition={condition} />}
        </>
      ) : (
        <p className={styles.bookSummaryUnknown}>Book info unavailable</p>
      )}
      <div className={styles.shippingStatus}>
        <ShippingStatus
          shipped={shipped}
          shippedAt={shippedAt}
          trackingNumber={trackingNumber}
          received={received}
        />
      </div>
    </div>
  );
}

function ShippingStatus({ shipped, shippedAt, trackingNumber, received }) {
  if (received) {
    return <span className="badge badge-green">Received</span>;
  }
  if (shipped) {
    return (
      <div>
        <span className="badge badge-amber">Shipped</span>
        {shippedAt && (
          <p style={{ fontSize: '0.75rem', color: 'var(--color-gray-500)', marginTop: '0.25rem' }}>
            {format(new Date(shippedAt), 'MMM d, yyyy')}
          </p>
        )}
        {trackingNumber && (
          <p style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--color-gray-600)', marginTop: '0.125rem' }}>
            {trackingNumber}
          </p>
        )}
      </div>
    );
  }
  return <span className="badge badge-gray">Not shipped</span>;
}
