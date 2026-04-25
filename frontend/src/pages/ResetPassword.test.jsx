import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import ResetPassword from './ResetPassword.jsx';

vi.mock('../services/api.js', () => ({
    auth: {
        confirmPasswordReset: vi.fn(),
    },
}));

import { auth } from '../services/api.js';

// Helper: render with optional search params
function renderResetPassword(search = '') {
    return renderWithProviders(<ResetPassword />, {
        route: `/reset-password${search}`,
    });
}

describe('ResetPassword page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    // -------------------------------------------------------------------------
    // Invalid link states
    // -------------------------------------------------------------------------

    it('shows invalid-link message when uid and token are missing', () => {
        renderResetPassword('');
        expect(screen.getByText(/invalid or incomplete/i)).toBeInTheDocument();
    });

    it('shows invalid-link message when only uid is present', () => {
        renderResetPassword('?uid=abc123');
        expect(screen.getByText(/invalid or incomplete/i)).toBeInTheDocument();
    });

    it('shows invalid-link message when only token is present', () => {
        renderResetPassword('?token=tok123');
        expect(screen.getByText(/invalid or incomplete/i)).toBeInTheDocument();
    });

    it('shows a "request new reset link" link when params are missing', () => {
        renderResetPassword('');
        expect(
            screen.getByRole('link', { name: /request a new reset link/i })
        ).toBeInTheDocument();
    });

    it('does NOT render the password form when the link is invalid', () => {
        renderResetPassword('');
        expect(screen.queryByLabelText(/new password/i)).not.toBeInTheDocument();
    });

    // -------------------------------------------------------------------------
    // Valid link — form renders
    // -------------------------------------------------------------------------

    it('renders the password form when uid and token are both present', () => {
        renderResetPassword('?uid=abc123&token=tok456');
        expect(screen.getByLabelText('New password')).toBeInTheDocument();
        expect(screen.getByLabelText(/confirm new password/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /reset password/i })).toBeInTheDocument();
    });

    // -------------------------------------------------------------------------
    // Client-side validation
    // -------------------------------------------------------------------------

    it('shows required error when password fields are empty', async () => {
        renderResetPassword('?uid=abc123&token=tok456');
        await userEvent.click(screen.getByRole('button', { name: /reset password/i }));
        expect(await screen.findByText(/password is required/i)).toBeInTheDocument();
    });

    it('shows min-length error for passwords shorter than 8 characters', async () => {
        renderResetPassword('?uid=abc123&token=tok456');
        await userEvent.type(screen.getByLabelText('New password'), 'short');
        await userEvent.click(screen.getByRole('button', { name: /reset password/i }));
        expect(await screen.findByText(/at least 8 characters/i)).toBeInTheDocument();
    });

    it('shows mismatch error when passwords do not match', async () => {
        renderResetPassword('?uid=abc123&token=tok456');
        await userEvent.type(screen.getByLabelText('New password'), 'password123');
        await userEvent.type(screen.getByLabelText(/confirm new password/i), 'different123');
        await userEvent.click(screen.getByRole('button', { name: /reset password/i }));
        expect(await screen.findByText(/passwords do not match/i)).toBeInTheDocument();
    });

    // -------------------------------------------------------------------------
    // Success flow
    // -------------------------------------------------------------------------

    it('shows success message and hides the form after successful submission', async () => {
        auth.confirmPasswordReset.mockResolvedValue({ data: {} });
        renderResetPassword('?uid=abc123&token=tok456');

        await userEvent.type(screen.getByLabelText('New password'), 'newpassword1');
        await userEvent.type(screen.getByLabelText(/confirm new password/i), 'newpassword1');
        await userEvent.click(screen.getByRole('button', { name: /reset password/i }));

        expect(await screen.findByText(/password has been reset successfully/i)).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /reset password/i })).not.toBeInTheDocument();
    });

    it('shows a "continue to sign in" link after success', async () => {
        auth.confirmPasswordReset.mockResolvedValue({ data: {} });
        renderResetPassword('?uid=abc123&token=tok456');

        await userEvent.type(screen.getByLabelText('New password'), 'newpassword1');
        await userEvent.type(screen.getByLabelText(/confirm new password/i), 'newpassword1');
        await userEvent.click(screen.getByRole('button', { name: /reset password/i }));

        await waitFor(() => {
            expect(screen.getByRole('link', { name: /continue to sign in/i })).toBeInTheDocument();
        });
    });

    it('calls confirmPasswordReset with uid, token, and passwords', async () => {
        auth.confirmPasswordReset.mockResolvedValue({ data: {} });
        renderResetPassword('?uid=abc123&token=tok456');

        await userEvent.type(screen.getByLabelText('New password'), 'newpassword1');
        await userEvent.type(screen.getByLabelText(/confirm new password/i), 'newpassword1');
        await userEvent.click(screen.getByRole('button', { name: /reset password/i }));

        await waitFor(() => {
            expect(auth.confirmPasswordReset).toHaveBeenCalledWith({
                uid: 'abc123',
                token: 'tok456',
                new_password: 'newpassword1',
                new_password2: 'newpassword1',
            });
        });
    });

    // -------------------------------------------------------------------------
    // Server error handling
    // -------------------------------------------------------------------------

    it('shows a detail string from the server error', async () => {
        auth.confirmPasswordReset.mockRejectedValue({
            response: { data: { detail: 'This reset link has expired.' } },
        });
        renderResetPassword('?uid=abc123&token=tok456');

        await userEvent.type(screen.getByLabelText('New password'), 'newpassword1');
        await userEvent.type(screen.getByLabelText(/confirm new password/i), 'newpassword1');
        await userEvent.click(screen.getByRole('button', { name: /reset password/i }));

        expect(await screen.findByText(/reset link has expired/i)).toBeInTheDocument();
    });

    it('flattens field-level error objects from the server', async () => {
        auth.confirmPasswordReset.mockRejectedValue({
            response: { data: { new_password: ['This password is too common.'] } },
        });
        renderResetPassword('?uid=abc123&token=tok456');

        await userEvent.type(screen.getByLabelText('New password'), 'newpassword1');
        await userEvent.type(screen.getByLabelText(/confirm new password/i), 'newpassword1');
        await userEvent.click(screen.getByRole('button', { name: /reset password/i }));

        expect(await screen.findByText(/too common/i)).toBeInTheDocument();
    });

    it('shows a generic fallback when the error has no parseable detail', async () => {
        auth.confirmPasswordReset.mockRejectedValue(new Error('Network error'));
        renderResetPassword('?uid=abc123&token=tok456');

        await userEvent.type(screen.getByLabelText('New password'), 'newpassword1');
        await userEvent.type(screen.getByLabelText(/confirm new password/i), 'newpassword1');
        await userEvent.click(screen.getByRole('button', { name: /reset password/i }));

        expect(await screen.findByText(/unable to reset password/i)).toBeInTheDocument();
    });

    // -------------------------------------------------------------------------
    // Loading state
    // -------------------------------------------------------------------------

    it('disables the submit button while the request is in-flight', async () => {
        let resolve;
        auth.confirmPasswordReset.mockReturnValue(new Promise((r) => { resolve = r; }));
        renderResetPassword('?uid=abc123&token=tok456');

        await userEvent.type(screen.getByLabelText('New password'), 'newpassword1');
        await userEvent.type(screen.getByLabelText(/confirm new password/i), 'newpassword1');
        await userEvent.click(screen.getByRole('button', { name: /reset password/i }));

        expect(await screen.findByRole('button', { name: /resetting/i })).toBeDisabled();
        resolve({ data: {} });
    });
});
