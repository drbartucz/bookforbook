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

    const [profileForm, setProfileForm] = useState({
        username: '',
        account_type: 'individual',
        institution_name: '',
    });
    const [profileSuccess, setProfileSuccess] = useState(null);
    const [profileError, setProfileError] = useState(null);

    const [addressForm, setAddressForm] = useState({
        full_name: '',
        address_line_1: '',
        address_line_2: '',
        city: '',
        state: '',
        zip_code: '',
    });

    const [institutionForm, setInstitutionForm] = useState({
        institution_url: '',
        institution_about: '',
        institution_bookshop_url: '',
    });
    const [institutionError, setInstitutionError] = useState(null);
    const [institutionSuccess, setInstitutionSuccess] = useState(null);

    const { data: me, isLoading, isError, error, refetch } = useQuery({
        queryKey: ['me'],
        queryFn: () => usersApi.getMe().then((response) => response.data),
        staleTime: 1000 * 60 * 5,
    });

    useEffect(() => {
        if (!me) {
            return;
        }
        setProfileForm({
            username: me.username ?? '',
            account_type: me.account_type ?? 'individual',
            institution_name: me.institution_name ?? '',
        });
        setAddressForm({
            full_name: me.full_name ?? '',
            address_line_1: me.address_line_1 ?? '',
            address_line_2: me.address_line_2 ?? '',
            city: me.city ?? '',
            state: me.state ?? '',
            zip_code: me.zip_code ?? '',
        });
        setInstitutionForm({
            institution_url: me.institution_url ?? '',
            institution_about: me.institution_about ?? '',
            institution_bookshop_url: me.institution_bookshop_url ?? '',
        });
    }, [me]);

    const updateProfileMutation = useMutation({
        mutationFn: (payload) => usersApi.updateMe(payload).then((response) => response.data),
        onSuccess: async (updatedMe) => {
            setProfileError(null);
            setProfileSuccess('Profile updated successfully.');
            queryClient.setQueryData(['me'], updatedMe);
            updateUser({ ...(user ?? {}), ...updatedMe });
        },
        onError: (mutationError) => {
            const responseData = mutationError?.response?.data;
            setProfileSuccess(null);
            if (typeof responseData?.detail === 'string') {
                setProfileError(responseData.detail);
                return;
            }
            if (responseData && typeof responseData === 'object') {
                const fieldMessage = Object.values(responseData).flat().find(Boolean);
                if (fieldMessage) {
                    setProfileError(String(fieldMessage));
                    return;
                }
            }
            setProfileError('Could not update profile. Please try again.');
        },
    });

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

    const updateInstitutionMutation = useMutation({
        mutationFn: (payload) => usersApi.updateMe(payload).then((response) => response.data),
        onSuccess: async (updatedMe) => {
            setInstitutionError(null);
            setInstitutionSuccess('Institution profile updated.');
            queryClient.setQueryData(['me'], updatedMe);
            updateUser({ ...(user ?? {}), ...updatedMe });
        },
        onError: (mutationError) => {
            const responseData = mutationError?.response?.data;
            if (typeof responseData?.detail === 'string') {
                setInstitutionError(responseData.detail);
                return;
            }
            if (responseData && typeof responseData === 'object') {
                const fieldMessage = Object.values(responseData).flat().find(Boolean);
                if (fieldMessage) {
                    setInstitutionError(String(fieldMessage));
                    return;
                }
            }
            setInstitutionError('Could not save institution profile. Please try again.');
        },
    });

    function handleProfileChange(event) {
        const { name, value } = event.target;
        setProfileSuccess(null);
        setProfileError(null);
        setProfileForm((current) => ({ ...current, [name]: value }));
    }

    function handleProfileSubmit(event) {
        event.preventDefault();
        updateProfileMutation.mutate(profileForm);
    }

    function handleAddressChange(event) {
        const { name, value } = event.target;
        setSuccessMessage(null);
        setServerError(null);
        setAddressForm((current) => ({
            ...current,
            [name]: name === 'state' ? value.toUpperCase() : value,
        }));
    }

    function handleAddressSubmit(event) {
        event.preventDefault();
        setServerError(null);
        setSuccessMessage(null);
        verifyAddressMutation.mutate({
            full_name: addressForm.full_name.trim(),
            address_line_1: addressForm.address_line_1.trim(),
            address_line_2: addressForm.address_line_2.trim(),
            city: addressForm.city.trim(),
            state: addressForm.state.trim(),
            zip_code: addressForm.zip_code.trim(),
        });
    }

    function handleInstitutionChange(event) {
        const { name, value } = event.target;
        setInstitutionError(null);
        setInstitutionSuccess(null);
        setInstitutionForm((current) => ({ ...current, [name]: value }));
    }

    function handleInstitutionSubmit(event) {
        event.preventDefault();
        setInstitutionError(null);
        setInstitutionSuccess(null);
        const bookshopUrl = institutionForm.institution_bookshop_url.trim();
        if (bookshopUrl) {
            try {
                const host = new URL(bookshopUrl).hostname.replace(/^www\./, '');
                if (host !== 'bookshop.org') {
                    setInstitutionError('Only bookshop.org URLs are accepted for the wishlist link.');
                    return;
                }
            } catch {
                setInstitutionError('Please enter a valid bookshop.org URL.');
                return;
            }
        }
        updateInstitutionMutation.mutate({
            institution_url: institutionForm.institution_url.trim() || null,
            institution_about: institutionForm.institution_about.trim() || null,
            institution_bookshop_url: institutionForm.institution_bookshop_url.trim() || null,
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
                    <p className="page-subtitle">Manage your account profile and shipping address.</p>
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
                    <h2 className={styles.sectionTitle}>Account profile</h2>
                    <p className={styles.helperText}>
                        Your email and username are used for login and identification. Libraries and bookstores should update their account type here.
                    </p>

                    {profileError && <div className="alert alert-error">{profileError}</div>}
                    {profileSuccess && <div className="alert alert-success">{profileSuccess}</div>}

                    <form className={styles.form} onSubmit={handleProfileSubmit}>
                        <div className="form-group">
                            <label className="form-label" htmlFor="username">Username</label>
                            <input
                                id="username"
                                name="username"
                                className="form-input"
                                value={profileForm.username}
                                onChange={handleProfileChange}
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label" htmlFor="email">Email</label>
                            <input
                                id="email"
                                name="email"
                                className="form-input"
                                value={account?.email ?? ''}
                                disabled
                                title="Email cannot be changed."
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label">Account type</label>
                            <div style={{ display: 'flex', gap: '1rem', marginTop: '0.25rem' }}>
                                {[
                                    { value: 'individual', label: 'Individual' },
                                    { value: 'library', label: 'Library' },
                                    { value: 'bookstore', label: 'Bookstore' },
                                ].map((opt) => (
                                    <label key={opt.value} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.875rem' }}>
                                        <input
                                            type="radio"
                                            name="account_type"
                                            value={opt.value}
                                            checked={profileForm.account_type === opt.value}
                                            onChange={handleProfileChange}
                                        />
                                        {opt.label}
                                    </label>
                                ))}
                            </div>
                        </div>

                        {(profileForm.account_type === 'library' || profileForm.account_type === 'bookstore') && (
                            <div className="form-group">
                                <label className="form-label" htmlFor="institution_name">Institution name</label>
                                <input
                                    id="institution_name"
                                    name="institution_name"
                                    className="form-input"
                                    value={profileForm.institution_name}
                                    onChange={handleProfileChange}
                                    placeholder="e.g. City Public Library"
                                    required
                                />
                            </div>
                        )}

                        <div className={styles.actions}>
                            <button type="submit" className="btn btn-primary" disabled={updateProfileMutation.isPending}>
                                {updateProfileMutation.isPending ? 'Saving...' : 'Save profile changes'}
                            </button>
                        </div>
                    </form>

                    <div style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid var(--color-gray-100)' }}>
                        <dl className={styles.infoList}>
                            <div>
                                <dt>
                                    Match capacity
                                    <Tooltip content="New accounts start with 2 active match slots. Complete trades and earn ratings to unlock up to 10 simultaneous matches." />
                                </dt>
                                <dd>{account?.max_active_matches ?? 2} slots</dd>
                            </div>
                            <div>
                                <dt>Verification status</dt>
                                <dd>{account?.is_verified ? 'Verified Institution' : 'Standard Account'}</dd>
                            </div>
                        </dl>
                    </div>
                </div>

                <div className={`card ${styles.panel}`}>
                    <h2 className={styles.sectionTitle}>Shipping address</h2>
                    <p className={styles.helperText}>
                        We verify US addresses with USPS before saving them so trades can reveal shipping details immediately when needed.
                    </p>

                    {serverError && <div className="alert alert-error">{serverError}</div>}
                    {successMessage && <div className="alert alert-success">{successMessage}</div>}

                    <form className={styles.form} onSubmit={handleAddressSubmit}>
                        <div className="form-group">
                            <label className="form-label" htmlFor="full_name">Full name</label>
                            <input
                                id="full_name"
                                name="full_name"
                                className="form-input"
                                value={addressForm.full_name}
                                onChange={handleAddressChange}
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
                                value={addressForm.address_line_1}
                                onChange={handleAddressChange}
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
                                value={addressForm.address_line_2}
                                onChange={handleAddressChange}
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
                                    value={addressForm.city}
                                    onChange={handleAddressChange}
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
                                    value={addressForm.state}
                                    onChange={handleAddressChange}
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
                                    value={addressForm.zip_code}
                                    onChange={handleAddressChange}
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

            {(account?.account_type === 'library' || account?.account_type === 'bookstore') && (
                <div className={`card ${styles.panel}`}>
                    <h2 className={styles.sectionTitle}>Institution profile</h2>
                    <p className={styles.helperText}>
                        This information is shown publicly on your institution profile and the institutions directory.
                    </p>

                    {institutionError && <div className="alert alert-error">{institutionError}</div>}
                    {institutionSuccess && <div className="alert alert-success">{institutionSuccess}</div>}

                    <form className={styles.form} onSubmit={handleInstitutionSubmit}>
                        <div className="form-group">
                            <label className="form-label" htmlFor="institution_url">Website URL</label>
                            <input
                                id="institution_url"
                                name="institution_url"
                                type="url"
                                className="form-input"
                                value={institutionForm.institution_url}
                                onChange={handleInstitutionChange}
                                placeholder="https://example.org"
                                autoComplete="url"
                            />
                        </div>
                        <div className="form-group">
                            <label className="form-label" htmlFor="institution_about">About Us</label>
                            <textarea
                                id="institution_about"
                                name="institution_about"
                                className={`form-input ${styles.textarea}`}
                                value={institutionForm.institution_about}
                                onChange={handleInstitutionChange}
                                rows={5}
                                placeholder="Tell readers about your institution, your collection, and what kinds of books you're looking for..."
                            />
                        </div>
                        <div className="form-group">
                            <label className="form-label" htmlFor="institution_bookshop_url">Bookshop.org wishlist URL (optional)</label>
                            <input
                                id="institution_bookshop_url"
                                name="institution_bookshop_url"
                                type="url"
                                className="form-input"
                                value={institutionForm.institution_bookshop_url}
                                onChange={handleInstitutionChange}
                                placeholder="https://bookshop.org/wishlists/..."
                                autoComplete="off"
                            />
                        </div>
                        <div className={styles.actions}>
                            <button type="submit" className="btn btn-primary" disabled={updateInstitutionMutation.isPending}>
                                {updateInstitutionMutation.isPending ? 'Saving...' : 'Save institution profile'}
                            </button>
                        </div>
                    </form>
                </div>
            )}

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
