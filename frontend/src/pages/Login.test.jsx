import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Login from './Login.jsx';

// Mock the API module
vi.mock('../services/api.js', () => ({
    auth: {
        login: vi.fn(),
    },
    users: {
        getMe: vi.fn(),
    },
}));

// Mock useAuth so we can inspect the login action
vi.mock('../hooks/useAuth.js', () => ({
    default: vi.fn(),
}));

import { auth as authApi, users as usersApi } from '../services/api.js';
import useAuth from '../hooks/useAuth.js';

const mockLogin = vi.fn();
const mockUpdateUser = vi.fn();

beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({
        login: mockLogin,
        updateUser: mockUpdateUser,
        isAuthenticated: false,
    });
});

describe('Login page', () => {
    it('renders email and password fields and submit button', () => {
        renderWithProviders(<Login />);
        expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
    });

    it('shows validation error when fields are empty', async () => {
        renderWithProviders(<Login />);
        await userEvent.click(screen.getByRole('button', { name: /sign in/i }));
        await waitFor(() => {
            expect(screen.getByText('Email is required.')).toBeInTheDocument();
        });
    });

    it('calls authApi.login and login action on successful submission', async () => {
        authApi.login.mockResolvedValueOnce({
            data: { access: 'access-token', refresh: 'refresh-token' },
        });
        usersApi.getMe.mockResolvedValueOnce({
            data: { id: '1', username: 'alice', account_type: 'individual' },
        });

        renderWithProviders(<Login />);

        await userEvent.type(screen.getByLabelText(/email address/i), 'alice@example.com');
        await userEvent.type(screen.getByLabelText(/password/i), 'correct-pass');
        await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

        await waitFor(() => {
            expect(authApi.login).toHaveBeenCalledWith({
                email: 'alice@example.com',
                password: 'correct-pass',
            });
            expect(mockLogin).toHaveBeenCalledWith(
                { access: 'access-token', refresh: 'refresh-token' },
                null
            );
            expect(mockUpdateUser).toHaveBeenCalledWith({
                id: '1',
                username: 'alice',
                account_type: 'individual',
            });
        });
    });

    it('shows server error message from data.detail on failure', async () => {
        authApi.login.mockRejectedValueOnce({
            response: { data: { detail: 'No active account found with the given credentials.' } },
        });

        renderWithProviders(<Login />);

        await userEvent.type(screen.getByLabelText(/email address/i), 'bad@example.com');
        await userEvent.type(screen.getByLabelText(/password/i), 'wrong-pass');
        await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

        await waitFor(() => {
            expect(
                screen.getByText('No active account found with the given credentials.')
            ).toBeInTheDocument();
        });
    });

    it('shows fallback error message when no detail in response', async () => {
        authApi.login.mockRejectedValueOnce({ response: { data: {} } });

        renderWithProviders(<Login />);

        await userEvent.type(screen.getByLabelText(/email address/i), 'bad@example.com');
        await userEvent.type(screen.getByLabelText(/password/i), 'wrong-pass');
        await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

        await waitFor(() => {
            expect(
                screen.getByText('Invalid email or password. Please try again.')
            ).toBeInTheDocument();
        });
    });

    it('disables the submit button while submitting', async () => {
        // Never resolve so we can inspect the loading state
        authApi.login.mockReturnValueOnce(new Promise(() => { }));

        renderWithProviders(<Login />);

        await userEvent.type(screen.getByLabelText(/email address/i), 'alice@example.com');
        await userEvent.type(screen.getByLabelText(/password/i), 'pass');
        await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

        await waitFor(() => {
            expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled();
        });
    });

    it('shows non_field_errors from response', async () => {
        authApi.login.mockRejectedValueOnce({
            response: { data: { non_field_errors: ['Invalid credentials.'] } },
        });

        renderWithProviders(<Login />);
        await userEvent.type(screen.getByLabelText(/email address/i), 'bad@example.com');
        await userEvent.type(screen.getByLabelText(/password/i), 'wrong-pass');
        await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

        await waitFor(() => expect(screen.getByText('Invalid credentials.')).toBeInTheDocument());
    });

    it('proceeds without user profile when getMe fails after login', async () => {
        authApi.login.mockResolvedValueOnce({
            data: { access: 'access-token', refresh: 'refresh-token' },
        });
        usersApi.getMe.mockRejectedValueOnce(new Error('Network error'));

        renderWithProviders(<Login />);
        await userEvent.type(screen.getByLabelText(/email address/i), 'alice@example.com');
        await userEvent.type(screen.getByLabelText(/password/i), 'correct-pass');
        await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

        // Should succeed (navigate) even if getMe fails
        await waitFor(() => expect(mockLogin).toHaveBeenCalled());
    });

    it('reads the "from" redirect path from location state (covers left side of || in line 15)', async () => {
        authApi.login.mockResolvedValueOnce({
            data: { access: 'access-token', refresh: 'refresh-token' },
        });
        usersApi.getMe.mockResolvedValueOnce({
            data: { id: '1', username: 'alice', account_type: 'individual' },
        });

        // Pass location.state.from.pathname so the left branch of `|| '/dashboard'` executes
        renderWithProviders(<Login />, {
            route: { pathname: '/login', state: { from: { pathname: '/matches' } } },
        });

        await userEvent.type(screen.getByLabelText(/email address/i), 'alice@example.com');
        await userEvent.type(screen.getByLabelText(/password/i), 'correct-pass');
        await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

        await waitFor(() => expect(mockLogin).toHaveBeenCalled());
    });
});
