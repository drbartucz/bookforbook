import React, { useState, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation } from '@tanstack/react-query';
import { Turnstile } from '@marsidev/react-turnstile';
import { notifications as notificationsApi } from '../services/api.js';
import styles from './Contact.module.css';

const SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY || '1x00000000000000000000AA';

export default function Contact() {
  const [turnstileToken, setTurnstileToken] = useState(null);
  const turnstileRef = useRef(null);
  
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm();

  const mutation = useMutation({
    mutationFn: (data) => notificationsApi.contactSubmit({ ...data, turnstile_token: turnstileToken }),
    onSuccess: () => {
      reset();
      setTurnstileToken(null);
      turnstileRef.current?.reset();
    },
    onError: () => {
      setTurnstileToken(null);
      turnstileRef.current?.reset();
    },
  });

  const onSubmit = (data) => {
    mutation.mutate(data);
  };

  return (
    <div className={styles.container}>
      <div className={styles.formWrapper}>
        <header className={styles.header}>
          <h1 className={styles.title}>Contact Us</h1>
          <p className={styles.subtitle}>
            Have a question or feedback? We&apos;d love to hear from you.
          </p>
        </header>

        {mutation.isSuccess ? (
          <div className={styles.successMessage}>
            <span className={styles.successIcon}>✅</span>
            <h2>Message Sent!</h2>
            <p>Thank you for reaching out. Our team will get back to you as soon as possible.</p>
            <button 
              className="btn btn-primary" 
              onClick={() => mutation.reset()}
            >
              Send another message
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} className={styles.form}>
            <div className={styles.field}>
              <label htmlFor="name">Name</label>
              <input
                id="name"
                type="text"
                placeholder="Your name"
                {...register('name', { required: 'Name is required' })}
                disabled={mutation.isPending}
              />
              {errors.name && <span className={styles.error}>{errors.name.message}</span>}
            </div>

            <div className={styles.field}>
              <label htmlFor="email">Email Address</label>
              <input
                id="email"
                type="email"
                placeholder="you@example.com"
                {...register('email', { 
                  required: 'Email is required',
                  pattern: {
                    value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                    message: 'Invalid email address'
                  }
                })}
                disabled={mutation.isPending}
              />
              {errors.email && <span className={styles.error}>{errors.email.message}</span>}
            </div>

            <div className={styles.field}>
              <label htmlFor="message">Message</label>
              <textarea
                id="message"
                placeholder="How can we help you?"
                rows={5}
                {...register('message', { required: 'Message is required' })}
                disabled={mutation.isPending}
              />
              {errors.message && <span className={styles.error}>{errors.message.message}</span>}
            </div>

            <div className={styles.captchaWrapper}>
              <Turnstile
                ref={turnstileRef}
                siteKey={SITE_KEY}
                onSuccess={(token) => setTurnstileToken(token)}
                onExpire={() => setTurnstileToken(null)}
                onError={() => setTurnstileToken(null)}
              />
            </div>

            {mutation.isError && (
              <div className="alert alert-error">
                {mutation.error.response?.data?.detail || 'Something went wrong. Please try again.'}
              </div>
            )}

            <button
              type="submit"
              className="btn btn-primary btn-block"
              disabled={mutation.isPending || !turnstileToken}
            >
              {mutation.isPending ? 'Sending...' : 'Send Message'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
