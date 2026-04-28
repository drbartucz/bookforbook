import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { users as usersApi } from '../services/api.js';
import useAuth from '../hooks/useAuth.js';
import LoadingSpinner from '../components/common/LoadingSpinner.jsx';
import Tooltip from '../components/common/Tooltip.jsx';
import styles from './AccountSettings.module.css';

function getAddressStatusLabel(status) {
    if (status === 'verified') return 'Verified';
    if (status === 'failed') return 'Needs review';
    return 'Not verified';
}

function getAddressStatusHelp(status) {
    if (status === 'verified') {
        return 'Your shipping address is verified and ready for matches and proposals.';
    }
    if (status === 'failed') {
        return 'Your last USPS verification failed. Review the error details and re-submit your address.';
    }
    return 'Verify your shipping address to accept matches and proposals.';
}

export default function AccountSettings() {
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const { user, updateUser, logout } = useAuth();
    const [serverError, setServerError] = useState(null);
    const [successMessage, setSuccessMessage] = useState(null);
    const [deletePassword, setDeletePassword] = useState('');
    const [deleteError, setDeleteError] = useState(null);
    const [form, setForm] = useState({
        full_name: '',
        address_line_1: '',
        address_line_2: '',
        city: '',
        state: '',
        zip_code: '',
    });

    const { data: me, isLoading, isError, error, refetch } = useQuery({
        queryKey: ['me'],
        queryFn: () => usersApi.getMe().then((response) => response.data),
        staleTime: 1000 * 60 * 5,
    });

    useEffect(() => {
        if (!me) {
            return;
        }
        setForm({
            full_name: me.full_name ?? '',
            address_line_1: me.address_line_1 ?? '',
            address_line_2: me.address_line_2 ?? '',
            city: me.city ?? '',
            state: me.state ?? '',
            zip_code: me.zip_code ?? '',
        });
    }, [me]);

    const verifyAddressMutation = useMutation({
        mutationFn: (payload) => usersApi.verifyAddress(payload).then((response) => response.data),
        onSuccess: async () => {
            setServerError(null);
            setSuccessMessage('Address verified and saved.');
            const refreshedUser = await queryClient.fetchQuery({
                queryKey: ['me'],
                queryFn: () => usersApi.getMe().then((response) => response.data),
            });
            updateUser({ ...(user ?? {}), ...refreshedUser });
            queryClient.setQueryData(['me'], refreshedUser);
        },
        onError: (mutationError) => {
            const responseData = mutationError?.response?.data;
            if (typeof responseData?.detail === 'string') {
                setServerError(responseData.detail);
                return;
            }
            if (responseData && typeof responseData === 'object') {
                const fieldMessage = Object.values(responseData)
                    .flat()
                    .find(Boolean);
                if (fieldMessage) {
                    setServerError(String(fieldMessage));
                    return;
                }
            }
            setServerError('Unable to verify address with USPS. Please check your address and try again.');
        },
    });

    const deleteAccountMutation = useMutation({
        mutationFn: (payload) => usersApi.deleteAccount(payload),
        onSuccess: () => {
            logout();
            navigate('/login', { replace: true });
        },
        onError: (mutationError) => {
            const responseData = mutationError?.response?.data;
            if (typeof responseData?.detail === 'string') {
                setDeleteError(responseData.detail);
                return;
            }
            if (responseData && typeof responseData === 'object') {
                const fieldMessage = Object.values(responseData).flat().find(Boolean);
                if (fieldMessage) {
                    setDeleteError(String(fieldMessage));
                    return;
                }
            }
            setDeleteError('Unable to delete account. Please try again.');
        },
    });

    function handleChange(event) {
        const { name, value } = event.target;
        setSuccessMessage(null);
        setServerError(null);
        setForm((current) => ({
            ...current,
            [name]: name === 'state' ? value.toUpperCase() : value,
        }));
    }

    function handleSubmit(event) {
        event.preventDefault();
        setServerError(null);
        setSuccessMessage(null);
        verifyAddressMutation.mutate({
            full_name: form.full_name.trim(),
            address_line_1: form.address_line_1.trim(),
            address_line_2: form.address_line_2.trim(),
            city: form.city.trim(),
            state: form.state.trim(),
            zip_code: form.zip_code.trim(),
        });
    }

    function handleDeleteAccount(event) {
        event.preventDefault();
        setDeleteError(null);
        if (!deletePassword.trim()) {
            setDeleteError('Password is required to delete your account.');
            return;
        }
        deleteAccountMutation.mutate({ password: deletePassword });
    }

    if (isLoading) {
        return <LoadingSpinner center size="lg" />;
    }

    if (isError) {
        return (
            <div className={styles.page}>
                <div className={`card ${styles.panel}`}>
                    <h1 className="page-title">Account settings</h1>
                    <div className="alert alert-error">
                        {error?.response?.data?.detail || 'Unable to load your account settings.'}
                    </div>
                    <button type="button" className="btn btn-secondary" onClick={() => refetch()}>
                        Try again
                    </button>
                </div>
            </div>
        );
    }

    const account = me ?? user;
    const addressStatus = getAddressStatusLabel(account?.address_verification_status);
    const statusHelp = getAddressStatusHelp(account?.address_verification_status);
    const hasAddress = Boolean(account?.address_line_1 && account?.city && account?.state && account?.zip_code);

    return (
        <div className={styles.page}>
            <div className={styles.header}>
                <div>
                    <h1 className="page-title">Account settings</h1>
                    <p className="page-subtitle">Add and verify the shipping address used for trades and donations.</p>
                </div>
                <div className={styles.statusCard}>
                    <span className={`${styles.statusBadge} ${account?.address_verification_status === 'verified' ? styles.statusVerified : styles.statusPending}`}>
                        {addressStatus}
                    </span>
                    <p className={styles.statusText}>
                        {hasAddress
                            ? 'Your current address is stored here and can be re-verified any time.'
                            : 'No shipping address is on file yet.'}
                    </p>
                    <p className={styles.statusText}>{statusHelp}</p>
                    {account?.address_verification_status === 'failed' && serverError && (
                        <p className={styles.statusError}>Last USPS error: {serverError}</p>
                    )}
                </div>
            </div>

            <div className={styles.grid}>
                <div className={`card ${styles.panel}`}>
                    <h2 className={styles.sectionTitle}>Account</h2>
                    <dl className={styles.infoList}>
                        <div>
                            <dt>Username</dt>
                            <dd>@{account?.username}</dd>
                        </div>
                        <div>
                            <dt>Email</dt>
                            <dd>{account?.email}</dd>
                        </div>
                        <div>
                            <dt>Account type</dt>
                            <dd>{account?.account_type === 'institution' ? 'Institution' : 'Individual'}</dd>
                        </div>
                        {account?.institution_name && (
                            <div>
                                <dt>Institution</dt>
                                <dd>{account.institution_name}</dd>
                            </div>
                        )}
                        <div>
                            <dt>
                                Match capacity
                                <Tooltip content="New accounts start with 2 active match slots. Complete trades and earn ratings to unlock up to 10 simultaneous matches." />
                            </dt>
                            <dd>{account?.max_active_matches ?? 2} slots</dd>
                        </div>
                    </dl>
                </div>

                <div className={`card ${styles.panel}`}>
                    <h2 className={styles.sectionTitle}>Shipping address</h2>
                    <p className={styles.helperText}>
                        We verify US addresses with USPS before saving them so trades can reveal shipping details immediately when needed.
                    </p>

                    {serverError && <div className="alert alert-error">{serverError}</div>}
                    {successMessage && <div className="alert alert-success">{successMessage}</div>}

                    <form className={styles.form} onSubmit={handleSubmit}>
                        <div className="form-group">
                            <label className="form-label" htmlFor="full_name">Full name</label>
                            <input
                                id="full_name"
                                name="full_name"
                                className="form-input"
                                value={form.full_name}
                                onChange={handleChange}
                                autoComplete="name"
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label" htmlFor="address_line_1">Address line 1</label>
                            <input
                                id="address_line_1"
                                name="address_line_1"
                                className="form-input"
                                value={form.address_line_1}
                                onChange={handleChange}
                                autoComplete="address-line1"
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label" htmlFor="address_line_2">Address line 2</label>
                            <input
                                id="address_line_2"
                                name="address_line_2"
                                className="form-input"
                                value={form.address_line_2}
                                onChange={handleChange}
                                autoComplete="address-line2"
                            />
                        </div>

                        <div className={styles.row}>
                            <div className="form-group">
                                <label className="form-label" htmlFor="city">City</label>
                                <input
                                    id="city"
                                    name="city"
                                    className="form-input"
                                    value={form.city}
                                    onChange={handleChange}
                                    autoComplete="address-level2"
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label" htmlFor="state">
                                    State <Tooltip content="2-letter state abbreviation, e.g. CA, NY, TX. Continental US only (48 states)." />
                                </label>
                                <input
                                    id="state"
                                    name="state"
                                    className="form-input"
                                    value={form.state}
                                    onChange={handleChange}
                                    autoComplete="address-level1"
                                    maxLength={2}
                                    required
                                />
                            </div>
                            <div className="form-group">
                                <label className="form-label" htmlFor="zip_code">ZIP code</label>
                                <input
                                    id="zip_code"
                                    name="zip_code"
                                    className="form-input"
                                    value={form.zip_code}
                                    onChange={handleChange}
                                    autoComplete="postal-code"
                                    required
                                />
                            </div>
                        </div>

                        <div className={styles.actions}>
                            <button type="submit" className="btn btn-primary" disabled={verifyAddressMutation.isPending}>
                                {verifyAddressMutation.isPending ? 'Verifying...' : 'Verify and save address'}
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            <div className={`card ${styles.dangerZone}`}>
                <h2 className={styles.sectionTitle}>Danger Zone</h2>
                <p className={styles.helperText}>
                    Delete your account and deactivate access. This action cannot be undone.
                </p>

                {deleteError && <div className="alert alert-error">{deleteError}</div>}

                <form onSubmit={handleDeleteAccount} className={styles.deleteForm}>
                    <div className="form-group">
                        <label className="form-label" htmlFor="delete-password">Confirm password</label>
                        <input
                            id="delete-password"
                            type="password"
                            className="form-input"
                            value={deletePassword}
                            onChange={(event) => setDeletePassword(event.target.value)}
                            autoComplete="current-password"
                        />
                    </div>

                    <Tooltip content="Your active matches and trades will be cancelled. This cannot be undone.">
                        <button
                            type="submit"
                            className="btn btn-danger"
                            disabled={deleteAccountMutation.isPending}
                        >
                            {deleteAccountMutation.isPending ? 'Deleting account...' : 'Delete account'}
                        </button>
                    </Tooltip>
                </form>
            </div>
        </div>
    );
}