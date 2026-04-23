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

  const from = location.state?.from?.pathname || '/dashboard';

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm();

  async function onSubmit(data) {
    setServerError(null);
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
      const data = err?.response?.data;
      if (data?.detail) {
        setServerError(data.detail);
      } else if (data?.non_field_errors) {
        setServerError(data.non_field_errors.join(' '));
      } else {
        setServerError('Invalid email or password. Please try again.');
      }
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
