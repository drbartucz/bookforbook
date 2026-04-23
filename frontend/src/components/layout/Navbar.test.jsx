import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { renderWithProviders } from '../../test/renderWithProviders.jsx';
import Navbar from './Navbar.jsx';
import useAuth from '../../hooks/useAuth.js';
import { notifications as notificationsApi } from '../../services/api.js';

vi.mock('../../hooks/useAuth.js', () => ({
    default: vi.fn(),
}));

vi.mock('../../services/api.js', () => ({
    notifications: {
        counts: vi.fn(),
        list: vi.fn(),
        markAllRead: vi.fn(),
    },
}));

describe('Navbar', () => {
    beforeEach(() => {
        vi.clearAllMocks();

        useAuth.mockReturnValue({
            isAuthenticated: true,
            user: { id: 'u1', username: 'reader' },
            logout: vi.fn(),
        });

        notificationsApi.counts.mockResolvedValue({
            data: {
                total_pending: 1,
                unread_notifications: 2,
            },
        });

        notificationsApi.list.mockResolvedValue({
            data: {
                results: [
                    {
                        id: 101,
                        title: 'Trade update',
                        body: 'Your trade partner marked a book as shipped.',
                    },
                ],
            },
        });

        notificationsApi.markAllRead.mockResolvedValue({ data: { updated: 2 } });
    });

    it('opens notifications dropdown and renders recent items', async () => {
        renderWithProviders(<Navbar />);

        const bell = screen.getByRole('button', { name: /notifications/i });
        await userEvent.click(bell);

        expect(await screen.findByText('Trade update')).toBeInTheDocument();
        expect(screen.getByText(/marked a book as shipped/i)).toBeInTheDocument();
        expect(notificationsApi.list).toHaveBeenCalledWith({ page: 1, page_size: 5 });
    });

    it('marks all notifications as read from the dropdown', async () => {
        renderWithProviders(<Navbar />);

        const bell = screen.getByRole('button', { name: /notifications/i });
        await userEvent.click(bell);

        const markAllButton = await screen.findByRole('button', { name: /mark all read/i });
        await userEvent.click(markAllButton);

        await waitFor(() => {
            expect(notificationsApi.markAllRead).toHaveBeenCalledTimes(1);
        });
    });
});
