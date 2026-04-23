import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { auth as authApi } from '../services/api.js';
import styles from './Auth.module.css';

export default function ForgotPassword() {
    const [serverError, setServerError] = useState(null);
    const [success, setSuccess] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const {
        register,
        handleSubmit,
        formState: { errors },
    } = useForm();

    async function onSubmit(data) {
        setServerError(null);
        setIsSubmitting(true);
        try {
            await authApi.requestPasswordReset({ email: data.email });
            setSuccess(true);
        } catch (err) {
            const detail = err?.response?.data?.detail;
            setServerError(detail || 'Unable to request password reset. Please try again.');
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <div className={styles.pageWrapper}>
            <div className={`card ${styles.card}`}>
                <div className={styles.header}>
                    <h1 className={styles.title}>Reset your password</h1>
                    <p className={styles.subtitle}>Enter your account email to receive a reset link.</p>
                </div>

                {serverError && (
                    <div className="alert alert-error" style={{ margin: '0 1.5rem' }}>
                        {serverError}
                    </div>
                )}

                {success ? (
                    <div style={{ padding: '0 1.5rem 1.5rem' }}>
                        <div className="alert alert-success">
                            If an account exists for that email, a reset link has been sent.
                        </div>
                        <p className="form-hint" style={{ marginTop: '0.75rem' }}>
                            Check your inbox and spam folder, then open the reset link to set a new password.
                        </p>
                        <Link to="/login" className="btn btn-primary" style={{ marginTop: '1rem' }}>
                            Back to sign in
                        </Link>
                    </div>
                ) : (
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
                            {errors.email && <p className="form-error">{errors.email.message}</p>}
                        </div>

                        <button
                            type="submit"
                            className={`btn btn-primary btn-lg ${styles.submitBtn}`}
                            disabled={isSubmitting}
                        >
                            {isSubmitting ? 'Sending...' : 'Send reset link'}
                        </button>
                    </form>
                )}
            </div>
        </div>
    );
}
