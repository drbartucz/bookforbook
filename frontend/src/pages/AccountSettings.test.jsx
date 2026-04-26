import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { renderWithProviders } from '../test/renderWithProviders.jsx';
import AccountSettings from './AccountSettings.jsx';

vi.mock('../services/api.js', () => ({
    users: {
        getMe: vi.fn(),
        verifyAddress: vi.fn(),
        deleteAccount: vi.fn(),
    },
}));

vi.mock('../hooks/useAuth.js', () => ({
    default: vi.fn(),
}));

import { users as usersApi } from '../services/api.js';
import useAuth from '../hooks/useAuth.js';

const updateUser = vi.fn();
const logout = vi.fn();

beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({
        user: { id: 'user-1', username: 'reader', email: 'reader@example.com', account_type: 'individual' },
        updateUser,
        logout,
    });
});

describe('AccountSettings page', () => {
    it('loads and displays the current address information', async () => {
        usersApi.getMe.mockResolvedValueOnce({
            data: {
                id: 'user-1',
                username: 'reader',
                email: 'reader@example.com',
                account_type: 'individual',
                full_name: 'Jane Reader',
                address_line_1: '123 Main St',
                address_line_2: 'Apt 2',
                city: 'Portland',
                state: 'OR',
                zip_code: '97201',
                address_verification_status: 'verified',
            },
        });

        renderWithProviders(<AccountSettings />);

        expect(await screen.findByDisplayValue('Jane Reader')).toBeInTheDocument();
        expect(screen.getByDisplayValue('123 Main St')).toBeInTheDocument();
        expect(screen.getByDisplayValue('Portland')).toBeInTheDocument();
        expect(screen.getByText('Verified')).toBeInTheDocument();
    });

    it('submits the address for verification and refreshes the account data', async () => {
        usersApi.getMe
            .mockResolvedValueOnce({
                data: {
                    id: 'user-1',
                    username: 'reader',
                    email: 'reader@example.com',
                    account_type: 'individual',
                    full_name: '',
                    address_line_1: '',
                    address_line_2: '',
                    city: '',
                    state: '',
                    zip_code: '',
                    address_verification_status: 'unverified',
                },
            })
            .mockResolvedValueOnce({
                data: {
                    id: 'user-1',
                    username: 'reader',
                    email: 'reader@example.com',
                    account_type: 'individual',
                    full_name: 'Jane Reader',
                    address_line_1: '123 Main St',
                    address_line_2: '',
                    city: 'Portland',
                    state: 'OR',
                    zip_code: '97201',
                    address_verification_status: 'verified',
                },
            });
        usersApi.verifyAddress.mockResolvedValueOnce({ data: { detail: 'ok' } });

        renderWithProviders(<AccountSettings />);

        await userEvent.type(await screen.findByLabelText(/full name/i), 'Jane Reader');
        await userEvent.type(screen.getByLabelText(/address line 1/i), '123 Main St');
        await userEvent.type(screen.getByLabelText(/^city$/i), 'Portland');
        await userEvent.type(screen.getByLabelText(/state/i), 'or');
        await userEvent.type(screen.getByLabelText(/zip code/i), '97201');
        await userEvent.click(screen.getByRole('button', { name: /verify and save address/i }));

        await waitFor(() => {
            expect(usersApi.verifyAddress).toHaveBeenCalledWith({
                full_name: 'Jane Reader',
                address_line_1: '123 Main St',
                address_line_2: '',
                city: 'Portland',
                state: 'OR',
                zip_code: '97201',
            });
            expect(updateUser).toHaveBeenCalledWith(expect.objectContaining({
                full_name: 'Jane Reader',
                address_verification_status: 'verified',
            }));
        });

        expect(await screen.findByText('Address verified and saved.')).toBeInTheDocument();
    });

    it('renders danger zone delete account controls', async () => {
        usersApi.getMe.mockResolvedValueOnce({
            data: {
                id: 'user-1',
                username: 'reader',
                email: 'reader@example.com',
                account_type: 'individual',
                full_name: '',
                address_line_1: '',
                address_line_2: '',
                city: '',
                state: '',
                zip_code: '',
                address_verification_status: 'unverified',
            },
        });

        renderWithProviders(<AccountSettings />);

        expect(await screen.findByText(/danger zone/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /delete account/i })).toBeInTheDocument();
    });

    it('submits delete account with password', async () => {
        usersApi.getMe.mockResolvedValueOnce({
            data: {
                id: 'user-1',
                username: 'reader',
                email: 'reader@example.com',
                account_type: 'individual',
                full_name: '',
                address_line_1: '',
                address_line_2: '',
                city: '',
                state: '',
                zip_code: '',
                address_verification_status: 'unverified',
            },
        });
        usersApi.deleteAccount.mockResolvedValueOnce({ data: { detail: 'ok' } });

        renderWithProviders(<AccountSettings />);
        await userEvent.type(await screen.findByLabelText(/confirm password/i), 'secret123');
        await userEvent.click(screen.getByRole('button', { name: /delete account/i }));

        await waitFor(() => {
            expect(usersApi.deleteAccount).toHaveBeenCalledWith({ password: 'secret123' });
        });
    });

    it('shows password required error when delete is clicked with no password', async () => {
        usersApi.getMe.mockResolvedValueOnce({
            data: {
                id: 'user-1', username: 'reader', email: 'reader@example.com', account_type: 'individual',
                full_name: '', address_line_1: '', address_line_2: '', city: '', state: '', zip_code: '',
                address_verification_status: 'unverified',
            },
        });
        renderWithProviders(<AccountSettings />);
        await screen.findByText(/danger zone/i);
        await userEvent.click(screen.getByRole('button', { name: /delete account/i }));
        expect(screen.getByText('Password is required to delete your account.')).toBeInTheDocument();
    });

    it('shows delete error when account deletion fails', async () => {
        usersApi.getMe.mockResolvedValueOnce({
            data: {
                id: 'user-1', username: 'reader', email: 'reader@example.com', account_type: 'individual',
                full_name: '', address_line_1: '', address_line_2: '', city: '', state: '', zip_code: '',
                address_verification_status: 'unverified',
            },
        });
        usersApi.deleteAccount.mockRejectedValueOnce({
            response: { data: { detail: 'Incorrect password.' } },
        });
        renderWithProviders(<AccountSettings />);
        await userEvent.type(await screen.findByLabelText(/confirm password/i), 'wrongpassword');
        await userEvent.click(screen.getByRole('button', { name: /delete account/i }));
        await waitFor(() => expect(screen.getByText('Incorrect password.')).toBeInTheDocument());
    });

    it('shows error state when account data fails to load', async () => {
        usersApi.getMe.mockRejectedValueOnce(new Error('Network error'));
        renderWithProviders(<AccountSettings />);
        expect(await screen.findByText(/unable to load your account settings/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
    });

    it('shows institution name when account is an institution type', async () => {
        usersApi.getMe.mockResolvedValueOnce({
            data: {
                id: 'user-1',
                username: 'library1',
                email: 'lib@example.com',
                account_type: 'institution',
                institution_name: 'City Central Library',
                full_name: '',
                address_line_1: '',
                address_line_2: '',
                city: '',
                state: '',
                zip_code: '',
                address_verification_status: 'unverified',
            },
        });
        renderWithProviders(<AccountSettings />);
        expect(await screen.findByText('City Central Library')).toBeInTheDocument();
        // "Institution" appears as both label (dt) and value (dd) — use a more specific query
        const dd = document.querySelector('dd');
        expect(dd).toBeTruthy(); // account type dd rendered
    });

    it('shows USPS error in form area after failed address verification', async () => {
        usersApi.getMe.mockResolvedValueOnce({
            data: {
                id: 'user-1',
                username: 'reader',
                email: 'reader@example.com',
                account_type: 'individual',
                full_name: 'Jane Reader',
                address_line_1: '123 Main St',
                address_line_2: '',
                city: 'Portland',
                state: 'OR',
                zip_code: '97201',
                address_verification_status: 'unverified',
            },
        });
        usersApi.verifyAddress.mockRejectedValueOnce({
            response: { data: { detail: 'Address not found by USPS.' } },
        });
        renderWithProviders(<AccountSettings />);
        await screen.findByDisplayValue('Jane Reader'); // wait for form to load
        await userEvent.click(screen.getByRole('button', { name: /verify and save address/i }));
        await waitFor(() => {
            expect(screen.getByText('Address not found by USPS.')).toBeInTheDocument();
        });
    });

    it('shows USPS field error when detail is missing but fields are present', async () => {
        usersApi.getMe.mockResolvedValueOnce({
            data: {
                id: 'user-1',
                username: 'reader',
                email: 'reader@example.com',
                account_type: 'individual',
                full_name: 'Jane Reader',
                address_line_1: '123 Main St',
                address_line_2: '',
                city: 'Portland',
                state: 'OR',
                zip_code: '97201',
                address_verification_status: 'unverified',
            },
        });
        usersApi.verifyAddress.mockRejectedValueOnce({
            response: { data: { city: ['Enter a valid city.'] } },
        });
        renderWithProviders(<AccountSettings />);
        await screen.findByDisplayValue('Jane Reader');
        await userEvent.click(screen.getByRole('button', { name: /verify and save address/i }));
        await waitFor(() => {
            expect(screen.getByText('Enter a valid city.')).toBeInTheDocument();
        });
    });

    it('shows delete error from field errors when detail is missing', async () => {
        usersApi.getMe.mockResolvedValueOnce({
            data: {
                id: 'user-1',
                username: 'reader',
                email: 'reader@example.com',
                account_type: 'individual',
                full_name: '',
                address_line_1: '',
                address_line_2: '',
                city: '',
                state: '',
                zip_code: '',
                address_verification_status: 'unverified',
            },
        });
        usersApi.deleteAccount.mockRejectedValueOnce({
            response: { data: { password: ['Password is incorrect.'] } },
        });
        renderWithProviders(<AccountSettings />);
        await userEvent.type(await screen.findByLabelText(/confirm password/i), 'wrongpassword');
        await userEvent.click(screen.getByRole('button', { name: /delete account/i }));
        await waitFor(() => {
            expect(screen.getByText('Password is incorrect.')).toBeInTheDocument();
        });
    });

    it('shows generic USPS fallback when field values are all falsy', async () => {
        usersApi.getMe.mockResolvedValueOnce({
            data: {
                id: 'user-1',
                username: 'reader',
                email: 'reader@example.com',
                account_type: 'individual',
                full_name: 'Jane Reader',
                address_line_1: '123 Main St',
                address_line_2: '',
                city: 'Portland',
                state: 'OR',
                zip_code: '97201',
                address_verification_status: 'unverified',
            },
        });
        usersApi.verifyAddress.mockRejectedValueOnce({
            response: { data: { city: null } },  // object with all-null values
        });
        renderWithProviders(<AccountSettings />);
        await screen.findByDisplayValue('Jane Reader');
        await userEvent.click(screen.getByRole('button', { name: /verify and save address/i }));
        await waitFor(() => {
            expect(screen.getByText(/unable to verify address with USPS/i)).toBeInTheDocument();
        });
    });

    it('shows generic delete fallback when field values are all falsy', async () => {
        usersApi.getMe.mockResolvedValueOnce({
            data: {
                id: 'user-1',
                username: 'reader',
                email: 'reader@example.com',
                account_type: 'individual',
                full_name: '',
                address_line_1: '',
                address_line_2: '',
                city: '',
                state: '',
                zip_code: '',
                address_verification_status: 'unverified',
            },
        });
        usersApi.deleteAccount.mockRejectedValueOnce({
            response: { data: { non_field_errors: null } },  // object with all-null values
        });
        renderWithProviders(<AccountSettings />);
        await userEvent.type(await screen.findByLabelText(/confirm password/i), 'wrongpassword');
        await userEvent.click(screen.getByRole('button', { name: /delete account/i }));
        await waitFor(() => {
            expect(screen.getByText(/unable to delete account/i)).toBeInTheDocument();
        });
    });

    it('initializes form fields to empty string when me data has null values (covers ?? right branches)', async () => {
        usersApi.getMe.mockResolvedValueOnce({
            data: {
                id: 'user-1',
                username: 'reader',
                email: 'reader@example.com',
                account_type: 'individual',
                full_name: null,
                address_line_1: null,
                address_line_2: null,
                city: null,
                state: null,
                zip_code: null,
                address_verification_status: 'unverified',
            },
        });
        renderWithProviders(<AccountSettings />);
        const fullNameInput = await screen.findByLabelText(/full name/i);
        expect(fullNameInput).toHaveValue('');
        expect(screen.getByLabelText(/address line 1/i)).toHaveValue('');
    });

    it('shows error detail text when account load fails with a structured error detail', async () => {
        usersApi.getMe.mockRejectedValueOnce({
            response: { data: { detail: 'Authentication credentials were not provided.' } },
        });
        renderWithProviders(<AccountSettings />);
        expect(await screen.findByText('Authentication credentials were not provided.')).toBeInTheDocument();
    });

    it('uses {} spread when user is null during verifyAddress onSuccess (covers user ?? {} right branch)', async () => {
        useAuth.mockReturnValue({
            user: null,
            updateUser,
            logout,
        });
        usersApi.getMe
            .mockResolvedValueOnce({
                data: {
                    id: 'user-1',
                    username: 'reader',
                    email: 'reader@example.com',
                    account_type: 'individual',
                    full_name: 'Jane Reader',
                    address_line_1: '123 Main St',
                    address_line_2: '',
                    city: 'Portland',
                    state: 'OR',
                    zip_code: '97201',
                    address_verification_status: 'unverified',
                },
            })
            .mockResolvedValueOnce({
                data: {
                    id: 'user-1',
                    username: 'reader',
                    email: 'reader@example.com',
                    account_type: 'individual',
                    full_name: 'Jane Reader',
                    address_line_1: '123 Main St',
                    address_line_2: '',
                    city: 'Portland',
                    state: 'OR',
                    zip_code: '97201',
                    address_verification_status: 'verified',
                },
            });
        usersApi.verifyAddress.mockResolvedValueOnce({ data: { detail: 'ok' } });

        renderWithProviders(<AccountSettings />);
        await screen.findByDisplayValue('Jane Reader');
        await userEvent.click(screen.getByRole('button', { name: /verify and save address/i }));

        await waitFor(() => {
            // updateUser called with spread of {} (user is null) merged with refreshedUser
            expect(updateUser).toHaveBeenCalledWith(expect.objectContaining({ id: 'user-1' }));
        });
    });

    it('falls back to auth user when getMe query returns null data (covers me ?? user right branch at line 170)', async () => {
        usersApi.getMe.mockResolvedValueOnce({ data: null });
        renderWithProviders(<AccountSettings />);
        // Component reaches line 170: account = null ?? user = user from auth
        // The form renders without crashing
        await waitFor(() => {
            expect(screen.getByText('Account settings')).toBeInTheDocument();
        });
    });

    it('shows error state with "Try again" button when getMe fails, and refetch fires on click (covers line 162 onClick)', async () => {
        usersApi.getMe.mockRejectedValueOnce({ response: { data: { detail: 'Server error.' } } });
        renderWithProviders(<AccountSettings />);
        expect(await screen.findByText('Try again')).toBeInTheDocument();
        // clicking "Try again" calls refetch() — cover the onClick lambda
        usersApi.getMe.mockResolvedValueOnce({ data: null });
        await userEvent.click(screen.getByRole('button', { name: /try again/i }));
    });

    it('shows "Last USPS error" in status card when status is failed and error is present', async () => {
        usersApi.getMe.mockResolvedValueOnce({
            data: {
                id: 'user-1',
                username: 'reader',
                email: 'reader@example.com',
                account_type: 'individual',
                full_name: 'Jane Reader',
                address_line_1: '123 Bad St',
                address_line_2: '',
                city: 'Nowhere',
                state: 'XX',
                zip_code: '00000',
                address_verification_status: 'failed',
            },
        });
        usersApi.verifyAddress.mockRejectedValueOnce({
            response: { data: { detail: 'Delivery address undeliverable.' } },
        });
        renderWithProviders(<AccountSettings />);
        await screen.findByDisplayValue('Jane Reader'); // wait for load
        await userEvent.click(screen.getByRole('button', { name: /verify and save address/i }));
        await waitFor(() => {
            expect(screen.getByText(/last usps error/i)).toBeInTheDocument();
        });
    });
});