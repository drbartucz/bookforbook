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
});