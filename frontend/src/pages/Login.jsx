import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { auth as authApi, users as usersApi } from '../services/api.js';
import useAuth from '../hooks/useAuth.js';
import styles from './Auth.module.css';

export default function Login() {
  const { login, updateUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [serverError, setServerError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [resendEmail, setResendEmail] = useState(null);
  const [resendStatus, setResendStatus] = useState(null);

  const from = location.state?.from?.pathname || '/dashboard';

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm();

  async function handleResend() {
    if (!resendEmail) return;
    setResendStatus('sending');
    try {
      await authApi.resendVerification({ email: resendEmail });
    } catch {
      // Swallow errors — the server always returns 200
    } finally {
      setResendStatus('sent');
    }
  }

  async function onSubmit(data) {
    setServerError(null);
    setResendEmail(null);
    setResendStatus(null);
    setIsSubmitting(true);
    try {
      const tokenRes = await authApi.login({
        email: data.email,
        password: data.password,
      });
      const { access, refresh } = tokenRes.data;

      login({ access, refresh }, null);

      // Fetch user profile
      let user = null;
      try {
        const meRes = await usersApi.getMe();
        user = meRes.data;
      } catch {
        // Profile fetch is optional — proceed anyway
      }

      if (user) {
        updateUser(user);
      }
      navigate(from, { replace: true });
    } catch (err) {
      const errData = err?.response?.data;
      if (errData?.detail) {
        setServerError(errData.detail);
      } else if (errData?.non_field_errors) {
        setServerError(errData.non_field_errors.join(' '));
      } else {
        setServerError('Invalid email or password. Please try again.');
      }
      setResendEmail(data.email);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className={styles.pageWrapper}>
      <div className={`card ${styles.card}`}>
        <div className={styles.header}>
          <h1 className={styles.title}>Welcome back</h1>
          <p className={styles.subtitle}>Sign in to your BookForBook account</p>
        </div>

        {serverError && (
          <div className="alert alert-error" style={{ margin: '0 1.5rem' }}>
            {serverError}
            {resendStatus === 'sent' ? (
              <p style={{ marginTop: '0.5rem', fontSize: '0.875rem' }}>
                Verification email sent — check your inbox.
              </p>
            ) : (
              <p style={{ marginTop: '0.5rem', fontSize: '0.875rem' }}>
                Can&apos;t log in?{' '}
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={resendStatus === 'sending'}
                  style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', textDecoration: 'underline', font: 'inherit', color: 'inherit' }}
                >
                  {resendStatus === 'sending' ? 'Sending…' : 'Resend verification email'}
                </button>
              </p>
            )}
          </div>
        )}

        <form className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
          <div className="form-group">
            <label className="form-label" htmlFor="email">
              Email address
            </label>
            <input
              id="email"
              type="email"
              className={`form-input ${errors.email ? 'error' : ''}`}
              autoComplete="email"
              {...register('email', {
                required: 'Email is required.',
                pattern: {
                  value: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
                  message: 'Enter a valid email address.',
                },
              })}
            />
            {errors.email && (
              <p className="form-error">{errors.email.message}</p>
            )}
          </div>

          <div className="form-group">
            <div className={styles.labelRow}>
              <label className="form-label" htmlFor="password">
                Password
              </label>
              <Link to="/forgot-password" className={styles.forgotLink}>
                Forgot password?
              </Link>
            </div>
            <input
              id="password"
              type="password"
              className={`form-input ${errors.password ? 'error' : ''}`}
              autoComplete="current-password"
              {...register('password', {
                required: 'Password is required.',
              })}
            />
            {errors.password && (
              <p className="form-error">{errors.password.message}</p>
            )}
          </div>

          <button
            type="submit"
            className={`btn btn-primary btn-lg ${styles.submitBtn}`}
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <div className={styles.footer}>
          <p>
            Don&apos;t have an account?{' '}
            <Link to="/register">Create one free</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
