import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Register from './Register.jsx';

vi.mock('../services/api.js', () => ({
    auth: {
        register: vi.fn(),
    },
}));

import { auth as authApi } from '../services/api.js';

beforeEach(() => {
    vi.clearAllMocks();
});

async function fillForm(options = {}) {
    const {
        email = 'newuser@example.com',
        username = 'newuser',
        password = 'securepass',
        confirmPassword = 'securepass',
    } = options;

    await userEvent.type(screen.getByLabelText(/email address/i), email);
    await userEvent.type(screen.getByLabelText(/^username$/i), username);
    await userEvent.type(screen.getByLabelText(/^password$/i), password);
    await userEvent.type(screen.getByLabelText(/confirm password/i), confirmPassword);
}

describe('Register page', () => {
    it('renders registration form fields', () => {
        renderWithProviders(<Register />);
        expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/^username$/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
    });

    it('shows "Check your email" screen on successful registration', async () => {
        authApi.register.mockResolvedValueOnce({ data: {} });

        renderWithProviders(<Register />);
        await fillForm();
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText(/check your email/i)).toBeInTheDocument();
        });
        expect(authApi.register).toHaveBeenCalledWith(expect.objectContaining({
            account_type: 'individual',
            institution_name: '',
            institution_url: '',
        }));
    });

    it('renders institution fields and submits institution payload for library account', async () => {
        authApi.register.mockResolvedValueOnce({ data: {} });

        renderWithProviders(<Register />);
        await userEvent.click(screen.getByLabelText(/library/i));

        expect(screen.getByLabelText(/institution name/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/institution website/i)).toBeInTheDocument();

        await fillForm();
        await userEvent.type(screen.getByLabelText(/institution name/i), 'City Library');
        await userEvent.type(screen.getByLabelText(/institution website/i), 'https://library.example.org');
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(authApi.register).toHaveBeenCalledWith(expect.objectContaining({
                account_type: 'library',
                institution_name: 'City Library',
                institution_url: 'https://library.example.org',
            }));
        });
    });

    it('shows Go to sign in link on success screen', async () => {
        authApi.register.mockResolvedValueOnce({ data: {} });

        renderWithProviders(<Register />);
        await fillForm();
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByRole('link', { name: /go to sign in/i })).toBeInTheDocument();
        });
    });

    it('shows server error detail on registration failure', async () => {
        authApi.register.mockRejectedValueOnce({
            response: { data: { detail: 'A user with this email already exists.' } },
        });

        renderWithProviders(<Register />);
        await fillForm();
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText('A user with this email already exists.')).toBeInTheDocument();
        });
    });

    it('shows email field error from server', async () => {
        authApi.register.mockRejectedValueOnce({
            response: { data: { email: ['Enter a valid email address.'] } },
        });

        renderWithProviders(<Register />);
        await fillForm();
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText(/Email:/)).toBeInTheDocument();
        });
    });

    it('shows client-side validation error when passwords do not match', async () => {
        renderWithProviders(<Register />);
        await fillForm({ password: 'password1', confirmPassword: 'password2' });
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText('Passwords do not match.')).toBeInTheDocument();
        });
    });

    it('shows client-side validation error for short username', async () => {
        renderWithProviders(<Register />);
        await fillForm({ username: 'ab' });
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText('Must be at least 3 characters.')).toBeInTheDocument();
        });
    });

    it('disables submit button while submitting', async () => {
        authApi.register.mockReturnValueOnce(new Promise(() => { }));

        renderWithProviders(<Register />);
        await fillForm();
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByRole('button', { name: /creating/i })).toBeDisabled();
        });
    });
});
