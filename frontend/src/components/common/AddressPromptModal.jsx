import React, { useState } from 'react';
import { users } from '../../services/api.js';

export default function AddressPromptModal({ open, onClose }) {
    const [step, setStep] = useState('prompt');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState(null);
    const [form, setForm] = useState({
        full_name: '',
        address_line_1: '',
        address_line_2: '',
        city: '',
        state: '',
        zip_code: '',
    });

    if (!open) {
        return null;
    }

    async function handleVerifyAddress(e) {
        e.preventDefault();
        setSubmitting(true);
        setError(null);
        try {
            await users.verifyAddress(form);
            onClose();
        } catch (err) {
            const msg =
                err?.response?.data?.detail ||
                'Unable to verify address with USPS. Please check your address and try again.';
            setError(msg);
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <div
            style={{
                position: 'fixed',
                inset: 0,
                background: 'rgba(17, 24, 39, 0.5)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 60,
                padding: '1rem',
            }}
            role="presentation"
            onMouseDown={(event) => {
                if (event.target === event.currentTarget) {
                    onClose();
                }
            }}
        >
            <div className="card" style={{ width: 'min(560px, 100%)', padding: '1.25rem' }} role="dialog" aria-modal="true">
                {step === 'prompt' ? (
                    <>
                        <h3 style={{ marginTop: 0 }}>Would you like to add your address now?</h3>
                        <p className="text-sm text-gray" style={{ marginBottom: '1rem' }}>
                            We will verify it with USPS so you can quickly accept matches and proposals later.
                        </p>
                        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                            <button type="button" className="btn btn-secondary" onClick={onClose}>
                                Not now
                            </button>
                            <button type="button" className="btn btn-primary" onClick={() => setStep('verify')}>
                                Add address
                            </button>
                        </div>
                    </>
                ) : (
                    <form onSubmit={handleVerifyAddress}>
                        <h3 style={{ marginTop: 0 }}>Verify Shipping Address</h3>
                        {error && <div className="alert alert-error">{error}</div>}

                        <div className="form-group">
                            <label className="form-label" htmlFor="fullName">Full name</label>
                            <input
                                id="fullName"
                                className="form-input"
                                value={form.full_name}
                                onChange={(e) => setForm((v) => ({ ...v, full_name: e.target.value }))}
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label" htmlFor="address1">Address line 1</label>
                            <input
                                id="address1"
                                className="form-input"
                                value={form.address_line_1}
                                onChange={(e) => setForm((v) => ({ ...v, address_line_1: e.target.value }))}
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label" htmlFor="address2">Address line 2 (optional)</label>
                            <input
                                id="address2"
                                className="form-input"
                                value={form.address_line_2}
                                onChange={(e) => setForm((v) => ({ ...v, address_line_2: e.target.value }))}
                            />
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '0.5rem' }}>
                            <div className="form-group">
                                <label className="form-label" htmlFor="city">City</label>
                                <input
                                    id="city"
                                    className="form-input"
                                    value={form.city}
                                    onChange={(e) => setForm((v) => ({ ...v, city: e.target.value }))}
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label" htmlFor="state">State</label>
                                <input
                                    id="state"
                                    className="form-input"
                                    value={form.state}
                                    maxLength={2}
                                    onChange={(e) => setForm((v) => ({ ...v, state: e.target.value.toUpperCase() }))}
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label" htmlFor="zip">ZIP</label>
                                <input
                                    id="zip"
                                    className="form-input"
                                    value={form.zip_code}
                                    onChange={(e) => setForm((v) => ({ ...v, zip_code: e.target.value }))}
                                    required
                                />
                            </div>
                        </div>

                        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                            <button type="button" className="btn btn-secondary" onClick={onClose} disabled={submitting}>
                                Skip for now
                            </button>
                            <button type="submit" className="btn btn-primary" disabled={submitting}>
                                {submitting ? 'Verifying...' : 'Verify with USPS'}
                            </button>
                        </div>
                    </form>
                )}
            </div>
        </div>
    );
}
