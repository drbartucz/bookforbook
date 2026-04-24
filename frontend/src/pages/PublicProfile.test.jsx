import React from 'react';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import PublicProfile from './PublicProfile.jsx';
import useAuth from '../hooks/useAuth.js';
import { useParams } from 'react-router-dom';

vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual('react-router-dom');
    return {
        ...actual,
        useParams: vi.fn(),
    };
});

vi.mock('../hooks/useAuth.js', () => ({
    default: vi.fn(),
}));

vi.mock('../services/api.js', () => ({
    users: {
        getPublicProfile: vi.fn(),
        getUserRatings: vi.fn(),
        getMe: vi.fn(),
        getUserOfferedBooks: vi.fn(),
        getUserWantedBooks: vi.fn(),
    },
    institutions: {
        getWantedList: vi.fn(),
    },
    wishlist: {
        list: vi.fn(),
        update: vi.fn(),
    },
}));

import { institutions, users, wishlist } from '../services/api.js';

describe('PublicProfile page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        useParams.mockReturnValue({ id: 'institution-1' });
        useAuth.mockReturnValue({ isAuthenticated: false, user: null });
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        users.getUserOfferedBooks.mockResolvedValue({ data: [] });
        users.getUserWantedBooks.mockResolvedValue({ data: [] });
    });

    it('renders institution wanted books from the current API shape', async () => {
        users.getPublicProfile.mockResolvedValue({
            data: {
                id: 'institution-1',
                username: 'central-library',
                account_type: 'institution',
                is_verified: true,
                total_trades: 12,
            },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        institutions.getWantedList.mockResolvedValue({
            data: [
                {
                    id: 'wanted-1',
                    min_condition: 'good',
                    quantity_needed: 2,
                    book: {
                        id: 'book-1',
                        title: 'Beloved',
                        authors: ['Toni Morrison'],
                        cover_image_url: 'https://example.com/beloved.jpg',
                    },
                },
            ],
        });

        renderWithProviders(<PublicProfile />);

        expect(await screen.findByText('Beloved')).toBeInTheDocument();
        expect(screen.getByText('Toni Morrison')).toBeInTheDocument();
        expect(screen.getByAltText('Beloved')).toHaveAttribute('src', 'https://example.com/beloved.jpg');
        expect(screen.getByText(/Need: 2/)).toBeInTheDocument();
    });

    it('shows shipping address when viewing your own profile', async () => {
        useParams.mockReturnValue({ id: 'user-1' });
        useAuth.mockReturnValue({ isAuthenticated: true, user: { id: 'user-1' } });

        users.getPublicProfile.mockResolvedValue({
            data: {
                id: 'user-1',
                username: 'reader',
                account_type: 'individual',
                is_verified: true,
                total_trades: 3,
            },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        users.getMe.mockResolvedValue({
            data: {
                id: 'user-1',
                full_name: 'Jane Reader',
                address_line_1: '123 Main St',
                address_line_2: 'Apt 2',
                city: 'Portland',
                state: 'OR',
                zip_code: '97201',
                address_verification_status: 'verified',
            },
        });
        wishlist.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'wish-1',
                        min_condition: 'good',
                        edition_preference: 'same_language',
                        allow_translations: false,
                        exclude_abridged: true,
                        format_preferences: [],
                    },
                ],
            },
        });

        renderWithProviders(<PublicProfile />);

        expect(await screen.findByText('Shipping Address')).toBeInTheDocument();
        expect(screen.getByText('123 Main St')).toBeInTheDocument();
        expect(screen.getByText('Portland, OR 97201')).toBeInTheDocument();
        expect(screen.getByText('Edit address')).toHaveAttribute('href', '/account');
        expect(screen.getByText('Wishlist Match Preferences')).toBeInTheDocument();
        expect(screen.getByText('Applied to 1 current item')).toBeInTheDocument();
    });

    it('does not show shipping address on another user profile', async () => {
        useParams.mockReturnValue({ id: 'institution-1' });
        useAuth.mockReturnValue({ isAuthenticated: true, user: { id: 'user-1' } });

        users.getPublicProfile.mockResolvedValue({
            data: {
                id: 'institution-1',
                username: 'central-library',
                account_type: 'institution',
                is_verified: true,
                total_trades: 12,
            },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        institutions.getWantedList.mockResolvedValue({ data: [] });

        renderWithProviders(<PublicProfile />);

        expect(await screen.findByText('@central-library')).toBeInTheDocument();
        expect(screen.queryByText('Shipping Address')).not.toBeInTheDocument();
        expect(screen.queryByText('Wishlist Match Preferences')).not.toBeInTheDocument();
        expect(users.getMe).not.toHaveBeenCalled();
        expect(wishlist.list).not.toHaveBeenCalled();
    });

    it('does not show shipping address when viewing another individual user profile', async () => {
        useParams.mockReturnValue({ id: 'user-2' });
        useAuth.mockReturnValue({ isAuthenticated: true, user: { id: 'user-1' } });

        users.getPublicProfile.mockResolvedValue({
            data: {
                id: 'user-2',
                username: 'another-reader',
                account_type: 'individual',
                is_verified: true,
                total_trades: 4,
            },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });

        renderWithProviders(<PublicProfile />);

        expect(await screen.findByText('@another-reader')).toBeInTheDocument();
        expect(screen.queryByText('Shipping Address')).not.toBeInTheDocument();
        expect(screen.queryByText('Wishlist Match Preferences')).not.toBeInTheDocument();
        expect(users.getMe).not.toHaveBeenCalled();
        expect(wishlist.list).not.toHaveBeenCalled();
    });

    it('pre-populates wishlist match preferences with defaults when no wishlist items exist', async () => {
        useParams.mockReturnValue({ id: 'user-1' });
        useAuth.mockReturnValue({ isAuthenticated: true, user: { id: 'user-1' } });

        users.getPublicProfile.mockResolvedValue({
            data: {
                id: 'user-1',
                username: 'reader',
                account_type: 'individual',
                is_verified: true,
                total_trades: 3,
            },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        users.getMe.mockResolvedValue({
            data: {
                id: 'user-1',
                full_name: '',
                address_line_1: '',
                city: '',
                state: '',
                zip_code: '',
                address_verification_status: 'unverified',
            },
        });
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });

        renderWithProviders(<PublicProfile />);

        expect(await screen.findByText('Wishlist Match Preferences')).toBeInTheDocument();
        expect(screen.getByLabelText('Minimum acceptable condition')).toHaveValue('any');
        expect(screen.getByLabelText('Edition matching')).toHaveValue('same_language');
        expect(screen.getByText('Defaults for future items')).toBeInTheDocument();
    });

    it('applies updated wishlist preferences to existing wishlist items', async () => {
        useParams.mockReturnValue({ id: 'user-1' });
        useAuth.mockReturnValue({ isAuthenticated: true, user: { id: 'user-1' } });

        users.getPublicProfile.mockResolvedValue({
            data: {
                id: 'user-1',
                username: 'reader',
                account_type: 'individual',
                is_verified: true,
                total_trades: 3,
            },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        users.getMe.mockResolvedValue({
            data: {
                id: 'user-1',
                full_name: '',
                address_line_1: '',
                city: '',
                state: '',
                zip_code: '',
                address_verification_status: 'unverified',
            },
        });
        wishlist.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'wish-1',
                        min_condition: 'good',
                        edition_preference: 'same_language',
                        allow_translations: false,
                        exclude_abridged: true,
                        format_preferences: [],
                    },
                ],
            },
        });
        wishlist.update.mockResolvedValue({ data: {} });

        renderWithProviders(<PublicProfile />);

        await screen.findByText('Wishlist Match Preferences');
        await userEvent.selectOptions(screen.getByLabelText('Edition matching'), 'custom');
        await userEvent.click(screen.getByLabelText('Include translations'));
        await userEvent.click(screen.getByRole('button', { name: 'Hardcover' }));
        await userEvent.click(screen.getByRole('button', { name: 'Save wishlist preferences' }));

        expect(wishlist.update).toHaveBeenCalledWith(
            'wish-1',
            expect.objectContaining({
                edition_preference: 'custom',
                allow_translations: true,
                exclude_abridged: true,
                format_preferences: ['hardcover'],
            })
        );
    });

    it('shows offered books on any user profile', async () => {
        useParams.mockReturnValue({ id: 'user-2' });
        useAuth.mockReturnValue({ isAuthenticated: false, user: null });

        users.getPublicProfile.mockResolvedValue({
            data: {
                id: 'user-2',
                username: 'reader2',
                account_type: 'individual',
                is_verified: false,
                total_trades: 1,
            },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        users.getUserOfferedBooks.mockResolvedValue({
            data: [
                {
                    id: 'ub-1',
                    condition: 'good',
                    condition_notes: '',
                    status: 'available',
                    book: {
                        id: 'book-1',
                        title: 'Moby Dick',
                        authors: ['Herman Melville'],
                        cover_image_url: 'https://example.com/moby.jpg',
                    },
                },
            ],
        });

        renderWithProviders(<PublicProfile />);

        expect(await screen.findByText('Offered Books')).toBeInTheDocument();
        expect(await screen.findByText('Moby Dick')).toBeInTheDocument();
        expect(screen.getByText('Herman Melville')).toBeInTheDocument();
        expect(screen.getByAltText('Moby Dick')).toHaveAttribute('src', 'https://example.com/moby.jpg');
    });

    it('shows wanted books on an individual user profile', async () => {
        useParams.mockReturnValue({ id: 'user-2' });
        useAuth.mockReturnValue({ isAuthenticated: false, user: null });

        users.getPublicProfile.mockResolvedValue({
            data: {
                id: 'user-2',
                username: 'reader2',
                account_type: 'individual',
                is_verified: false,
                total_trades: 1,
            },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        users.getUserWantedBooks.mockResolvedValue({
            data: [
                {
                    id: 'wish-2',
                    min_condition: 'acceptable',
                    book: {
                        id: 'book-2',
                        title: 'The Great Gatsby',
                        authors: ['F. Scott Fitzgerald'],
                        cover_image_url: null,
                    },
                },
            ],
        });

        renderWithProviders(<PublicProfile />);

        expect(await screen.findByText('Wanted Books')).toBeInTheDocument();
        expect(await screen.findByText('The Great Gatsby')).toBeInTheDocument();
        expect(screen.getByText('F. Scott Fitzgerald')).toBeInTheDocument();
    });});
