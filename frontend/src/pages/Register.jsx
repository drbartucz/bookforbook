import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { auth as authApi } from '../services/api.js';
import styles from './Auth.module.css';

export default function Register() {
  const [success, setSuccess] = useState(false);
  const [serverError, setServerError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm({
    defaultValues: { account_type: 'individual' },
  });

  const password = watch('password');

  async function onSubmit(data) {
    setServerError(null);
    setIsSubmitting(true);
    try {
      await authApi.register({
        email: data.email,
        username: data.username,
        password: data.password,
        password2: data.confirmPassword,
        account_type: data.account_type,
      });
      setSuccess(true);
    } catch (err) {
      const resData = err?.response?.data;
      if (resData) {
        if (typeof resData === 'string') {
          setServerError(resData);
        } else if (resData.detail) {
          setServerError(resData.detail);
        } else if (resData.email) {
          setServerError(`Email: ${Array.isArray(resData.email) ? resData.email.join(' ') : resData.email}`);
        } else if (resData.username) {
          setServerError(`Username: ${Array.isArray(resData.username) ? resData.username.join(' ') : resData.username}`);
        } else if (resData.password) {
          setServerError(`Password: ${Array.isArray(resData.password) ? resData.password.join(' ') : resData.password}`);
        } else {
          setServerError('Registration failed. Please check your details and try again.');
        }
      } else {
        setServerError('Registration failed. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  if (success) {
    return (
      <div className={styles.pageWrapper}>
        <div className={`card ${styles.card}`}>
          <div className={styles.successBox}>
            <div className={styles.successIcon}>📬</div>
            <h1 className={styles.successTitle}>Check your email</h1>
            <p className={styles.successMessage}>
              We&apos;ve sent a verification link to your email address. Click the link to activate your account and start trading books.
            </p>
            <Link to="/login" className="btn btn-primary" style={{ marginTop: '1.5rem' }}>
              Go to sign in
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.pageWrapper}>
      <div className={`card ${styles.card}`}>
        <div className={styles.header}>
          <h1 className={styles.title}>Create your account</h1>
          <p className={styles.subtitle}>Join BookForBook — trade books 1-for-1, free.</p>
        </div>

        {serverError && (
          <div className="alert alert-error" style={{ margin: '0 1.5rem' }}>
            {serverError}
          </div>
        )}

        <form className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
          {/* Account type */}
          <div className="form-group">
            <label className="form-label">Account type</label>
            <div style={{ display: 'flex', gap: '1rem' }}>
              {[
                { value: 'individual', label: 'Individual' },
                { value: 'institution', label: 'Institution (library / bookstore)' },
              ].map((opt) => (
                <label
                  key={opt.value}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.375rem',
                    fontSize: '0.875rem',
                    cursor: 'pointer',
                  }}
                >
                  <input
                    type="radio"
                    value={opt.value}
                    {...register('account_type')}
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          </div>

          {/* Email */}
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
            {errors.email && <p className="form-error">{errors.email.message}</p>}
          </div>

          {/* Username */}
          <div className="form-group">
            <label className="form-label" htmlFor="username">
              Username
            </label>
            <input
              id="username"
              type="text"
              className={`form-input ${errors.username ? 'error' : ''}`}
              autoComplete="username"
              {...register('username', {
                required: 'Username is required.',
                minLength: { value: 3, message: 'Must be at least 3 characters.' },
                maxLength: { value: 30, message: 'Must be 30 characters or fewer.' },
                pattern: {
                  value: /^[a-zA-Z0-9_-]+$/,
                  message: 'Letters, numbers, hyphens, and underscores only.',
                },
              })}
            />
            {errors.username && <p className="form-error">{errors.username.message}</p>}
          </div>

          {/* Password */}
          <div className="form-group">
            <label className="form-label" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              className={`form-input ${errors.password ? 'error' : ''}`}
              autoComplete="new-password"
              {...register('password', {
                required: 'Password is required.',
                minLength: { value: 8, message: 'Must be at least 8 characters.' },
              })}
            />
            {errors.password && <p className="form-error">{errors.password.message}</p>}
            <p className="form-hint">At least 8 characters.</p>
          </div>

          {/* Confirm password */}
          <div className="form-group">
            <label className="form-label" htmlFor="confirmPassword">
              Confirm password
            </label>
            <input
              id="confirmPassword"
              type="password"
              className={`form-input ${errors.confirmPassword ? 'error' : ''}`}
              autoComplete="new-password"
              {...register('confirmPassword', {
                required: 'Please confirm your password.',
                validate: (val) => val === password || 'Passwords do not match.',
              })}
            />
            {errors.confirmPassword && (
              <p className="form-error">{errors.confirmPassword.message}</p>
            )}
          </div>

          <button
            type="submit"
            className={`btn btn-primary btn-lg ${styles.submitBtn}`}
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Creating account...' : 'Create account'}
          </button>

          <p className="form-hint" style={{ textAlign: 'center' }}>
            By signing up you agree to our Terms of Service.
          </p>
        </form>

        <div className={styles.footer}>
          <p>
            Already have an account? <Link to="/login">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
