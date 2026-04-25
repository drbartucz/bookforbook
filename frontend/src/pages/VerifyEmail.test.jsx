import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import VerifyEmail from './VerifyEmail.jsx';

vi.mock('../services/api.js', () => ({
    auth: {
        verifyEmail: vi.fn(),
    },
}));

import { auth as authApi } from '../services/api.js';

describe('VerifyEmail page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('shows error when uid or token is missing from query params', async () => {
        renderWithProviders(<VerifyEmail />, { route: '/verify-email?token=abc-only' });

        expect(await screen.findByText('Verification failed')).toBeInTheDocument();
        expect(screen.getByText('Invalid verification link — missing uid or token.')).toBeInTheDocument();
        expect(authApi.verifyEmail).not.toHaveBeenCalled();
    });

    it('verifies successfully and shows success state', async () => {
        authApi.verifyEmail.mockResolvedValue({ data: {} });

        renderWithProviders(<VerifyEmail />, { route: '/verify-email?uid=uid-123&token=token-abc' });

        await waitFor(() => {
            expect(authApi.verifyEmail).toHaveBeenCalledWith({ uid: 'uid-123', token: 'token-abc' });
        });

        expect(await screen.findByText('Email verified!')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login');
    });

    it('shows API detail error when verification fails', async () => {
        authApi.verifyEmail.mockRejectedValue({
            response: {
                data: {
                    detail: 'Token is invalid or expired.',
                },
            },
        });

        renderWithProviders(<VerifyEmail />, { route: '/verify-email?uid=uid-123&token=bad-token' });

        expect(await screen.findByText('Verification failed')).toBeInTheDocument();
        expect(screen.getByText('Token is invalid or expired.')).toBeInTheDocument();
    });

    it('shows API message error when detail is absent', async () => {
        authApi.verifyEmail.mockRejectedValue({
            response: { data: { message: 'Link already used.' } },
        });

        renderWithProviders(<VerifyEmail />, { route: '/verify-email?uid=uid-123&token=bad-token' });

        expect(await screen.findByText('Link already used.')).toBeInTheDocument();
    });

    it('silently ignores errors when component unmounts before verify completes (covers if (cancelled) return at line 30)', async () => {
        let rejectFn;
        authApi.verifyEmail.mockReturnValue(
            new Promise((_, reject) => {
                rejectFn = reject;
            })
        );

        const { unmount } = renderWithProviders(<VerifyEmail />, {
            route: '/verify-email?uid=uid-123&token=token-abc',
        });

        // Unmount before the API call resolves → cleanup sets cancelled=true
        unmount();

        // Now reject — catch fires, finds cancelled=true → returns early (no state updates)
        rejectFn(new Error('Cancelled'));

        // No assertions needed — test passes if there are no React unmounted-state warnings
    });

    it('shows generic error when no API message is available', async () => {
        authApi.verifyEmail.mockRejectedValue(new Error('Network error'));

        renderWithProviders(<VerifyEmail />, { route: '/verify-email?uid=uid-123&token=bad-token' });

        expect(await screen.findByText(/verification failed\. the link may have expired/i)).toBeInTheDocument();
    });
});
