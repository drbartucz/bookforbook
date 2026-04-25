import React from 'react';
import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import ForgotPassword from './ForgotPassword.jsx';

vi.mock('../services/api.js', () => ({
    auth: {
        requestPasswordReset: vi.fn(),
    },
}));

import { auth } from '../services/api.js';

describe('ForgotPassword page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders the email field and submit button', () => {
        renderWithProviders(<ForgotPassword />);
        expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /send reset link/i })).toBeInTheDocument();
    });

    it('shows a client-side error when submitted with an empty email', async () => {
        renderWithProviders(<ForgotPassword />);
        await userEvent.click(screen.getByRole('button', { name: /send reset link/i }));
        expect(await screen.findByText(/email is required/i)).toBeInTheDocument();
    });

    it('shows a client-side error for a malformed email', async () => {
        renderWithProviders(<ForgotPassword />);
        await userEvent.type(screen.getByLabelText(/email address/i), 'not-an-email');
        await userEvent.click(screen.getByRole('button', { name: /send reset link/i }));
        expect(await screen.findByText(/valid email/i)).toBeInTheDocument();
    });

    it('shows success message and hides the form on a successful submission', async () => {
        auth.requestPasswordReset.mockResolvedValue({ data: {} });
        renderWithProviders(<ForgotPassword />);

        await userEvent.type(screen.getByLabelText(/email address/i), 'user@example.com');
        await userEvent.click(screen.getByRole('button', { name: /send reset link/i }));

        expect(await screen.findByText(/reset link has been sent/i)).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /send reset link/i })).not.toBeInTheDocument();
    });

    it('shows the server error message on API failure', async () => {
        auth.requestPasswordReset.mockRejectedValue({
            response: { data: { detail: 'Too many attempts.' } },
        });
        renderWithProviders(<ForgotPassword />);

        await userEvent.type(screen.getByLabelText(/email address/i), 'user@example.com');
        await userEvent.click(screen.getByRole('button', { name: /send reset link/i }));

        expect(await screen.findByText(/too many attempts/i)).toBeInTheDocument();
    });

    it('shows a generic error when the API response has no detail', async () => {
        auth.requestPasswordReset.mockRejectedValue(new Error('Network error'));
        renderWithProviders(<ForgotPassword />);

        await userEvent.type(screen.getByLabelText(/email address/i), 'user@example.com');
        await userEvent.click(screen.getByRole('button', { name: /send reset link/i }));

        expect(await screen.findByText(/unable to request password reset/i)).toBeInTheDocument();
    });

    it('disables the submit button while the request is in-flight', async () => {
        let resolve;
        auth.requestPasswordReset.mockReturnValue(new Promise((r) => { resolve = r; }));
        renderWithProviders(<ForgotPassword />);

        await userEvent.type(screen.getByLabelText(/email address/i), 'user@example.com');
        await userEvent.click(screen.getByRole('button', { name: /send reset link/i }));

        expect(await screen.findByRole('button', { name: /sending/i })).toBeDisabled();

        await act(async () => { resolve({ data: {} }); });
        await waitFor(() =>
            expect(screen.queryByRole('button', { name: /sending/i })).not.toBeInTheDocument()
        );
    });

    it('shows a back-to-sign-in link after success', async () => {
        auth.requestPasswordReset.mockResolvedValue({ data: {} });
        renderWithProviders(<ForgotPassword />);

        await userEvent.type(screen.getByLabelText(/email address/i), 'user@example.com');
        await userEvent.click(screen.getByRole('button', { name: /send reset link/i }));

        await waitFor(() => {
            expect(screen.getByRole('link', { name: /back to sign in/i })).toBeInTheDocument();
        });
    });
});
