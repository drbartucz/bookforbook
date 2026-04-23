import React, { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { auth as authApi } from '../services/api.js';
import styles from './Auth.module.css';

export default function ResetPassword() {
    const [searchParams] = useSearchParams();
    const [serverError, setServerError] = useState(null);
    const [success, setSuccess] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const uid = searchParams.get('uid') || '';
    const token = searchParams.get('token') || '';

    const linkValid = useMemo(() => Boolean(uid && token), [uid, token]);

    const {
        register,
        handleSubmit,
        watch,
        formState: { errors },
    } = useForm();

    const password = watch('new_password');

    async function onSubmit(data) {
        if (!linkValid) {
            setServerError('This reset link is invalid or incomplete. Request a new reset link.');
            return;
        }

        setServerError(null);
        setIsSubmitting(true);
        try {
            await authApi.confirmPasswordReset({
                uid,
                token,
                new_password: data.new_password,
                new_password2: data.new_password2,
            });
            setSuccess(true);
        } catch (err) {
            const responseData = err?.response?.data;
            if (typeof responseData?.detail === 'string') {
                setServerError(responseData.detail);
            } else if (responseData && typeof responseData === 'object') {
                const fieldMessage = Object.values(responseData).flat().find(Boolean);
                setServerError(fieldMessage ? String(fieldMessage) : 'Unable to reset password.');
            } else {
                setServerError('Unable to reset password. Please request a new reset link.');
            }
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <div className={styles.pageWrapper}>
            <div className={`card ${styles.card}`}>
                <div className={styles.header}>
                    <h1 className={styles.title}>Choose a new password</h1>
                    <p className={styles.subtitle}>Set a secure password for your account.</p>
                </div>

                {serverError && (
                    <div className="alert alert-error" style={{ margin: '0 1.5rem' }}>
                        {serverError}
                    </div>
                )}

                {success ? (
                    <div style={{ padding: '0 1.5rem 1.5rem' }}>
                        <div className="alert alert-success">Your password has been reset successfully.</div>
                        <Link to="/login" className="btn btn-primary" style={{ marginTop: '1rem' }}>
                            Continue to sign in
                        </Link>
                    </div>
                ) : !linkValid ? (
                    <div style={{ padding: '0 1.5rem 1.5rem' }}>
                        <div className="alert alert-error">This reset link is invalid or incomplete.</div>
                        <Link to="/forgot-password" className="btn btn-secondary" style={{ marginTop: '1rem' }}>
                            Request a new reset link
                        </Link>
                    </div>
                ) : (
                    <form className={styles.form} onSubmit={handleSubmit(onSubmit)} noValidate>
                        <div className="form-group">
                            <label className="form-label" htmlFor="new_password">
                                New password
                            </label>
                            <input
                                id="new_password"
                                type="password"
                                className={`form-input ${errors.new_password ? 'error' : ''}`}
                                autoComplete="new-password"
                                {...register('new_password', {
                                    required: 'Password is required.',
                                    minLength: { value: 8, message: 'Must be at least 8 characters.' },
                                })}
                            />
                            {errors.new_password && <p className="form-error">{errors.new_password.message}</p>}
                        </div>

                        <div className="form-group">
                            <label className="form-label" htmlFor="new_password2">
                                Confirm new password
                            </label>
                            <input
                                id="new_password2"
                                type="password"
                                className={`form-input ${errors.new_password2 ? 'error' : ''}`}
                                autoComplete="new-password"
                                {...register('new_password2', {
                                    required: 'Please confirm your password.',
                                    validate: (val) => val === password || 'Passwords do not match.',
                                })}
                            />
                            {errors.new_password2 && <p className="form-error">{errors.new_password2.message}</p>}
                        </div>

                        <button
                            type="submit"
                            className={`btn btn-primary btn-lg ${styles.submitBtn}`}
                            disabled={isSubmitting}
                        >
                            {isSubmitting ? 'Resetting...' : 'Reset password'}
                        </button>
                    </form>
                )}
            </div>
        </div>
    );
}
