import React, { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { auth as authApi } from '../services/api.js';
import LoadingSpinner from '../components/common/LoadingSpinner.jsx';
import styles from './Auth.module.css';

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState('loading'); // 'loading' | 'success' | 'error'
  const [errorMsg, setErrorMsg] = useState('');

  const token = searchParams.get('token');
  const key = searchParams.get('key');

  useEffect(() => {
    const verificationKey = token || key;
    if (!verificationKey) {
      setStatus('error');
      setErrorMsg('No verification token found in the URL.');
      return;
    }

    let cancelled = false;

    authApi
      .verifyEmail({ token: verificationKey, key: verificationKey })
      .then(() => {
        if (!cancelled) setStatus('success');
      })
      .catch((err) => {
        if (cancelled) return;
        const msg =
          err?.response?.data?.detail ||
          err?.response?.data?.message ||
          'Verification failed. The link may have expired or already been used.';
        setErrorMsg(msg);
        setStatus('error');
      });

    return () => {
      cancelled = true;
    };
  }, [token, key]);

  return (
    <div className={styles.pageWrapper}>
      <div className={`card ${styles.card}`}>
        {status === 'loading' && (
          <div style={{ padding: '3rem', textAlign: 'center' }}>
            <LoadingSpinner size="lg" center />
            <p style={{ marginTop: '1rem', color: 'var(--color-gray-500)' }}>
              Verifying your email address...
            </p>
          </div>
        )}

        {status === 'success' && (
          <div className={styles.successBox}>
            <div className={styles.successIcon}>✅</div>
            <h1 className={styles.successTitle}>Email verified!</h1>
            <p className={styles.successMessage}>
              Your email address has been confirmed. You can now sign in and start trading books.
            </p>
            <Link to="/login" className="btn btn-primary" style={{ marginTop: '1.5rem' }}>
              Sign in
            </Link>
          </div>
        )}

        {status === 'error' && (
          <div className={styles.successBox}>
            <div className={styles.successIcon}>❌</div>
            <h1 className={styles.successTitle}>Verification failed</h1>
            <p className={styles.successMessage}>{errorMsg}</p>
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.5rem', justifyContent: 'center' }}>
              <Link to="/login" className="btn btn-secondary">
                Sign in
              </Link>
              <Link to="/register" className="btn btn-primary">
                Create account
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
