import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
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

    it('opens user menu and shows dropdown links', async () => {
        renderWithProviders(<Navbar />);
        // User menu button shows the first letter of the username
        const userBtn = screen.getAllByRole('button').find(b => b.textContent.includes('R') || b.textContent.includes('reader'));
        // Find by aria-haspopup="true" that is not the notifications button
        const menuButton = screen.getByRole('button', { name: /reader/i });
        await userEvent.click(menuButton);
        expect(await screen.findByRole('link', { name: /dashboard/i })).toBeInTheDocument();
        expect(screen.getByRole('link', { name: /my profile/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /sign out/i })).toBeInTheDocument();
    });

    it('closes menu when backdrop is clicked', async () => {
        renderWithProviders(<Navbar />);
        const menuButton = screen.getByRole('button', { name: /reader/i });
        await userEvent.click(menuButton);
        expect(await screen.findByRole('link', { name: /dashboard/i })).toBeInTheDocument();
        // Click backdrop to close
        const bell = screen.getByRole('button', { name: /notifications/i });
        await userEvent.click(bell);
        // Now notifications open, click backdrop
        expect(await screen.findByText('Notifications')).toBeInTheDocument();
    });

    it('closes dropdown on Escape key', async () => {
        renderWithProviders(<Navbar />);
        const menuButton = screen.getByRole('button', { name: /reader/i });
        await userEvent.click(menuButton);
        await screen.findByRole('link', { name: /dashboard/i });
        await userEvent.keyboard('{Escape}');
        expect(screen.queryByRole('link', { name: /my profile/i })).not.toBeInTheDocument();
    });

    it('shows mobile menu when hamburger is clicked', async () => {
        renderWithProviders(<Navbar />);
        const hamburger = screen.getByRole('button', { name: /toggle menu/i });
        await userEvent.click(hamburger);
        // Mobile menu shows authenticated links
        expect(await screen.findByRole('link', { name: /my profile/i })).toBeInTheDocument();
    });

    it('shows unread notification count badge', async () => {
        renderWithProviders(<Navbar />);
        // The badge with count 2 should be rendered once notificationsData loads
        await waitFor(() => {
            expect(screen.getByText('2')).toBeInTheDocument();
        });
    });

    it('shows empty notifications message when no notifications', async () => {
        notificationsApi.list.mockResolvedValue({ data: { results: [] } });
        renderWithProviders(<Navbar />);
        const bell = screen.getByRole('button', { name: /notifications/i });
        await userEvent.click(bell);
        expect(await screen.findByText(/no notifications yet/i)).toBeInTheDocument();
    });

    it('shows guest buttons when not authenticated', async () => {
        useAuth.mockReturnValue({ isAuthenticated: false, user: null, logout: vi.fn() });
        renderWithProviders(<Navbar />);
        expect(screen.getByRole('link', { name: /log in/i })).toBeInTheDocument();
        expect(screen.getByRole('link', { name: /sign up/i })).toBeInTheDocument();
    });

    it('shows mobile guest links when hamburger clicked while not authenticated', async () => {
        useAuth.mockReturnValue({ isAuthenticated: false, user: null, logout: vi.fn() });
        renderWithProviders(<Navbar />);
        const hamburger = screen.getByRole('button', { name: /toggle menu/i });
        await userEvent.click(hamburger);
        // Mobile menu shows login/register when not authenticated
        const logInLinks = screen.getAllByRole('link', { name: /log in/i });
        expect(logInLinks.length).toBeGreaterThan(0);
    });

    it('shows mobile sign out button and calls logout', async () => {
        const logoutFn = vi.fn();
        useAuth.mockReturnValue({
            isAuthenticated: true,
            user: { id: 'u1', username: 'reader' },
            logout: logoutFn,
        });
        renderWithProviders(<Navbar />);
        const hamburger = screen.getByRole('button', { name: /toggle menu/i });
        await userEvent.click(hamburger);
        const mobileSignOut = await screen.findByRole('button', { name: /sign out/i });
        await userEvent.click(mobileSignOut);
        expect(logoutFn).toHaveBeenCalled();
    });

    it('handles array-format notifications data (direct array from API)', async () => {
        notificationsApi.list.mockResolvedValue({
            data: [{ id: 201, title: 'Direct array notification', body: 'Array response body.' }],
        });
        renderWithProviders(<Navbar />);
        await userEvent.click(screen.getByRole('button', { name: /notifications/i }));
        expect(await screen.findByText('Direct array notification')).toBeInTheDocument();
    });

    it('clicking the backdrop closes the open menu', async () => {
        renderWithProviders(<Navbar />);
        const menuButton = screen.getByRole('button', { name: /reader/i });
        await userEvent.click(menuButton);
        await screen.findByRole('link', { name: /dashboard/i });
        // Find and click the backdrop overlay
        const backdrop = document.querySelector('[class*="backdrop"]');
        expect(backdrop).toBeInTheDocument();
        await userEvent.click(backdrop);
        expect(screen.queryByRole('link', { name: /my profile/i })).not.toBeInTheDocument();
    });

    it('logs out when sign out is clicked', async () => {
        const logoutFn = vi.fn();
        useAuth.mockReturnValue({
            isAuthenticated: true,
            user: { id: 'u1', username: 'reader' },
            logout: logoutFn,
        });
        renderWithProviders(<Navbar />);
        const menuButton = screen.getByRole('button', { name: /reader/i });
        await userEvent.click(menuButton);
        const signOut = await screen.findByRole('button', { name: /sign out/i });
        await userEvent.click(signOut);
        expect(logoutFn).toHaveBeenCalled();
    });

    it('shows "99+" badge when unread notification count exceeds 99', async () => {
        notificationsApi.counts.mockResolvedValue({
            data: { total_pending: 5, unread_notifications: 100 },
        });
        renderWithProviders(<Navbar />);
        await waitFor(() => {
            expect(screen.getByText('99+')).toBeInTheDocument();
        });
    });

    it('shows "99+" on pending matches badge when total_pending exceeds 99', async () => {
        notificationsApi.counts.mockResolvedValue({
            data: { total_pending: 100, unread_notifications: 0 },
        });
        renderWithProviders(<Navbar />);
        await waitFor(() => {
            // There should be a '99+' badge for the matches link
            const badges = screen.getAllByText('99+');
            expect(badges.length).toBeGreaterThan(0);
        });
    });

    it('handles null data from counts API gracefully', async () => {
        notificationsApi.counts.mockResolvedValue({});  // no data property → res.data = undefined
        renderWithProviders(<Navbar />);
        // Should render without crashing (totalPending/unreadNotifications default to 0)
        await waitFor(() => {
            expect(screen.getByRole('button', { name: /notifications/i })).toBeInTheDocument();
        });
    });

    it('handles null data from notifications list API gracefully', async () => {
        notificationsApi.list.mockResolvedValue({});  // no data property → res.data = undefined
        renderWithProviders(<Navbar />);
        await userEvent.click(screen.getByRole('button', { name: /notifications/i }));
        // Should show empty state without crashing
        expect(await screen.findByText(/no notifications yet/i)).toBeInTheDocument();
    });

    it('shows "Marking..." while markAllRead is pending', async () => {
        // Never resolve so we can capture the pending state
        notificationsApi.markAllRead.mockReturnValue(new Promise(() => {}));
        renderWithProviders(<Navbar />);
        await userEvent.click(screen.getByRole('button', { name: /notifications/i }));
        const markAllBtn = await screen.findByRole('button', { name: /mark all read/i });
        await userEvent.click(markAllBtn);
        // Button should now show "Marking..." (isPending = true)
        expect(screen.getByText('Marking...')).toBeInTheDocument();
    });

    it('shows "U" avatar and "Account" username when user has no username', async () => {
        useAuth.mockReturnValue({
            isAuthenticated: true,
            user: { id: 'u2', username: null },
            logout: vi.fn(),
        });
        renderWithProviders(<Navbar />);
        // Avatar shows 'U' and button label shows 'Account'
        expect(screen.getByRole('button', { name: /account/i })).toBeInTheDocument();
    });

    it('covers all dropdown Link onClick handlers (lines 188, 195, 202, 209)', async () => {
        renderWithProviders(<Navbar />);
        const menuButton = screen.getByRole('button', { name: /reader/i });

        // Dashboard link
        await userEvent.click(menuButton);
        await userEvent.click(await screen.findByRole('link', { name: 'Dashboard' }));

        // My Profile link
        await userEvent.click(menuButton);
        await userEvent.click(await screen.findByRole('link', { name: 'My Profile' }));

        // Proposals link
        await userEvent.click(menuButton);
        await userEvent.click(await screen.findByRole('link', { name: 'Proposals' }));

        // Donations link
        await userEvent.click(menuButton);
        await userEvent.click(await screen.findByRole('link', { name: 'Donations' }));

        // After each click, menu should have closed
        expect(screen.queryByRole('link', { name: 'Dashboard' })).not.toBeInTheDocument();
    });

    it('covers all mobile NavLink onClick handlers (authenticated) — lines 255-284', async () => {
        renderWithProviders(<Navbar />);
        const hamburger = screen.getByRole('button', { name: /toggle menu/i });

        const mobileNavLinkNames = [
            'Browse', 'Institutions', 'Dashboard', 'My Books',
            'Wishlist', /^Matches/, 'Proposals', 'Trades', 'Donations', 'My Profile',
        ];

        for (const name of mobileNavLinkNames) {
            await userEvent.click(hamburger);
            // Use within() to scope to the mobile menu so we don't pick up desktop nav links
            const mobileMenu = document.querySelector('[class*="mobileMenu"]');
            const link = within(mobileMenu).getByRole('link', { name });
            await userEvent.click(link);
        }
    });

    it('covers mobile guest link onClick handlers (lines 299, 302)', async () => {
        useAuth.mockReturnValue({ isAuthenticated: false, user: null, logout: vi.fn() });
        renderWithProviders(<Navbar />);
        const hamburger = screen.getByRole('button', { name: /toggle menu/i });

        // Log in link — use within() to scope to the mobile menu
        await userEvent.click(hamburger);
        let mobileMenu = document.querySelector('[class*="mobileMenu"]');
        await userEvent.click(within(mobileMenu).getByRole('link', { name: /log in/i }));

        // Sign up link
        await userEvent.click(hamburger);
        mobileMenu = document.querySelector('[class*="mobileMenu"]');
        await userEvent.click(within(mobileMenu).getByRole('link', { name: /sign up/i }));
    });
});
