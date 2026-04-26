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
    });

    it('displays ratings with stars, rater link, and comment', async () => {
        useParams.mockReturnValue({ id: 'user-2' });
        useAuth.mockReturnValue({ isAuthenticated: false, user: null });

        users.getPublicProfile.mockResolvedValue({
            data: {
                id: 'user-2',
                username: 'reader2',
                account_type: 'individual',
                is_verified: true,
                total_trades: 5,
            },
        });
        users.getUserRatings.mockResolvedValue({
            data: [
                {
                    id: 'rating-1',
                    score: 4,
                    comment: 'Great trade partner!',
                    created_at: '2026-04-01T00:00:00Z',
                    rater: { id: 'user-3', username: 'alice' },
                },
            ],
        });

        renderWithProviders(<PublicProfile />);

        expect(await screen.findByText('4/5')).toBeInTheDocument();
        expect(screen.getByText('Great trade partner!')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: '@alice' })).toBeInTheDocument();
    });

    it('renders a rating that has no comment (covers rating.comment false branch at line 357)', async () => {
        useParams.mockReturnValue({ id: 'user-2' });
        useAuth.mockReturnValue({ isAuthenticated: false, user: null });

        users.getPublicProfile.mockResolvedValue({
            data: { id: 'user-2', username: 'reader2', account_type: 'individual', is_verified: true, total_trades: 2 },
        });
        users.getUserRatings.mockResolvedValue({
            data: [
                {
                    id: 'rating-2',
                    score: 5,
                    comment: null,  // No comment — covers {rating.comment && <p>} false branch
                    created_at: null,
                    rater: { id: 'user-3', username: 'alice' },
                },
            ],
        });

        renderWithProviders(<PublicProfile />);
        expect(await screen.findByText('5/5')).toBeInTheDocument();
        expect(screen.queryByText(/ratingComment/)).not.toBeInTheDocument();
    });

    it('shows "Needs review" address status when verification has failed', async () => {
        useParams.mockReturnValue({ id: 'user-1' });
        useAuth.mockReturnValue({ isAuthenticated: true, user: { id: 'user-1' } });

        users.getPublicProfile.mockResolvedValue({
            data: { id: 'user-1', username: 'reader', account_type: 'individual', is_verified: true, total_trades: 3 },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        users.getMe.mockResolvedValue({
            data: {
                id: 'user-1',
                full_name: 'Jane Reader',
                address_line_1: '123 Main St',
                address_line_2: '',
                city: 'Portland',
                state: 'OR',
                zip_code: '97201',
                address_verification_status: 'failed',
            },
        });
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });

        renderWithProviders(<PublicProfile />);

        expect(await screen.findByText('Needs review')).toBeInTheDocument();
    });

    it('shows "No shipping address on file yet" when address is absent', async () => {
        useParams.mockReturnValue({ id: 'user-1' });
        useAuth.mockReturnValue({ isAuthenticated: true, user: { id: 'user-1' } });

        users.getPublicProfile.mockResolvedValue({
            data: { id: 'user-1', username: 'reader', account_type: 'individual', is_verified: true, total_trades: 0 },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        users.getMe.mockResolvedValue({
            data: { id: 'user-1', full_name: '', address_line_1: '', city: '', state: '', zip_code: '', address_verification_status: 'unverified' },
        });
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });

        renderWithProviders(<PublicProfile />);
        expect(await screen.findByText(/no shipping address on file yet/i)).toBeInTheDocument();
        expect(screen.getByRole('link', { name: /add address/i })).toBeInTheDocument();
    });

    it('shows display_name, bio, and location fields when present', async () => {
        useParams.mockReturnValue({ id: 'user-2' });
        useAuth.mockReturnValue({ isAuthenticated: false, user: null });

        users.getPublicProfile.mockResolvedValue({
            data: {
                id: 'user-2',
                username: 'reader2',
                account_type: 'individual',
                is_verified: false,
                total_trades: 2,
                display_name: 'Jane Reader',
                bio: 'I love science fiction.',
                location: 'Portland, OR',
            },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });

        renderWithProviders(<PublicProfile />);

        expect(await screen.findByText('Jane Reader')).toBeInTheDocument();
        expect(screen.getByText('I love science fiction.')).toBeInTheDocument();
        expect(screen.getByText(/Portland, OR/)).toBeInTheDocument();
    });

    it('shows avg_recent_rating stat and member since date when present', async () => {
        useParams.mockReturnValue({ id: 'user-2' });
        useAuth.mockReturnValue({ isAuthenticated: false, user: null });

        users.getPublicProfile.mockResolvedValue({
            data: {
                id: 'user-2',
                username: 'reader2',
                account_type: 'individual',
                is_verified: true,
                total_trades: 5,
                avg_recent_rating: 4.2,
                created_at: '2024-01-15T00:00:00Z',
            },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });

        renderWithProviders(<PublicProfile />);

        expect(await screen.findByText('Avg Rating')).toBeInTheDocument();
        expect(screen.getByText(/4\.2/)).toBeInTheDocument();
        expect(screen.getByText('Member since')).toBeInTheDocument();
        expect(screen.getByText(/Jan 2024/)).toBeInTheDocument();
    });

    it('shows "Not verified" address status when status is unverified but address is present', async () => {
        useParams.mockReturnValue({ id: 'user-1' });
        useAuth.mockReturnValue({ isAuthenticated: true, user: { id: 'user-1' } });

        users.getPublicProfile.mockResolvedValue({
            data: { id: 'user-1', username: 'reader', account_type: 'individual', is_verified: true, total_trades: 3 },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        users.getMe.mockResolvedValue({
            data: {
                id: 'user-1',
                full_name: 'Jane Reader',
                address_line_1: '123 Main St',
                address_line_2: '',
                city: 'Portland',
                state: 'OR',
                zip_code: '97201',
                address_verification_status: 'unverified',
            },
        });
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });

        renderWithProviders(<PublicProfile />);

        expect(await screen.findByText('Not verified')).toBeInTheDocument();
    });

    it('renders wanted book cover image when present', async () => {
        useParams.mockReturnValue({ id: 'user-2' });
        useAuth.mockReturnValue({ isAuthenticated: false, user: null });

        users.getPublicProfile.mockResolvedValue({
            data: { id: 'user-2', username: 'reader2', account_type: 'individual', is_verified: true, total_trades: 1 },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        users.getUserWantedBooks.mockResolvedValue({
            data: [
                {
                    id: 'wish-3',
                    min_condition: 'good',
                    book: {
                        id: 'book-3',
                        title: 'Invisible Man',
                        authors: ['Ralph Ellison'],
                        cover_image_url: 'https://example.com/invisible.jpg',
                    },
                },
            ],
        });

        renderWithProviders(<PublicProfile />);
        expect(await screen.findByAltText('Invisible Man')).toHaveAttribute('src', 'https://example.com/invisible.jpg');
    });

    it('shows error when wishlist preferences save fails', async () => {
        useParams.mockReturnValue({ id: 'user-1' });
        useAuth.mockReturnValue({ isAuthenticated: true, user: { id: 'user-1' } });

        users.getPublicProfile.mockResolvedValue({
            data: { id: 'user-1', username: 'reader', account_type: 'individual', is_verified: true, total_trades: 3 },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        users.getMe.mockResolvedValue({
            data: { id: 'user-1', full_name: '', address_line_1: '', city: '', state: '', zip_code: '', address_verification_status: 'unverified' },
        });
        wishlist.list.mockResolvedValue({
            data: {
                count: 1,
                results: [{ id: 'wish-1', min_condition: 'good', edition_preference: 'same_language', allow_translations: false, exclude_abridged: true, format_preferences: [] }],
            },
        });
        wishlist.update.mockRejectedValueOnce({
            response: { data: { detail: 'Update failed.' } },
        });

        renderWithProviders(<PublicProfile />);
        await screen.findByText('Wishlist Match Preferences');
        await userEvent.click(screen.getByRole('button', { name: 'Save wishlist preferences' }));
        expect(await screen.findByText('Update failed.')).toBeInTheDocument();
    });

    it('shows "Applied to N items" plural when wishlistItems.length > 1 (covers plural branch line 478)', async () => {
        useParams.mockReturnValue({ id: 'user-1' });
        useAuth.mockReturnValue({ isAuthenticated: true, user: { id: 'user-1' } });

        users.getPublicProfile.mockResolvedValue({
            data: { id: 'user-1', username: 'reader', account_type: 'individual', is_verified: true, total_trades: 0 },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        users.getMe.mockResolvedValue({
            data: { id: 'user-1', full_name: '', address_line_1: '', city: '', state: '', zip_code: '', address_verification_status: 'unverified' },
        });
        wishlist.list.mockResolvedValue({
            data: {
                count: 2,
                results: [
                    { id: 'wish-1', min_condition: 'good', edition_preference: 'same_language', allow_translations: false, exclude_abridged: true, format_preferences: [] },
                    { id: 'wish-2', min_condition: 'any', edition_preference: 'exact', allow_translations: true, exclude_abridged: false, format_preferences: [] },
                ],
            },
        });

        renderWithProviders(<PublicProfile />);
        expect(await screen.findByText('Applied to 2 current items')).toBeInTheDocument();
    });

    it('uses default edition_preference when wishlist item has no edition_preference (covers ?? right branch line 129)', async () => {
        useParams.mockReturnValue({ id: 'user-1' });
        useAuth.mockReturnValue({ isAuthenticated: true, user: { id: 'user-1' } });

        users.getPublicProfile.mockResolvedValue({
            data: { id: 'user-1', username: 'reader', account_type: 'individual', is_verified: true, total_trades: 0 },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        users.getMe.mockResolvedValue({
            data: { id: 'user-1', full_name: '', address_line_1: '', city: '', state: '', zip_code: '', address_verification_status: 'unverified' },
        });
        wishlist.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'wish-1',
                        min_condition: 'good',
                        // No edition_preference → falls back to DEFAULT_WISHLIST_PREFERENCES.edition_preference
                        allow_translations: false,
                        exclude_abridged: true,
                        format_preferences: [],
                    },
                ],
            },
        });

        renderWithProviders(<PublicProfile />);
        // Should render the wishlist preferences form with the default edition_preference
        expect(await screen.findByLabelText('Edition matching')).toHaveValue('same_language');
    });

    it('renders flat wantedBook (no nested .book) using item itself (covers ?? right branch line 449)', async () => {
        useParams.mockReturnValue({ id: 'user-2' });
        useAuth.mockReturnValue({ isAuthenticated: false, user: null });

        users.getPublicProfile.mockResolvedValue({
            data: { id: 'user-2', username: 'reader2', account_type: 'individual', is_verified: true, total_trades: 1 },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        users.getUserWantedBooks.mockResolvedValue({
            data: [
                {
                    id: 'wish-flat',
                    // No nested .book — item itself has book fields (flat structure)
                    title: 'Flat Wanted Book',
                    authors: ['Flat Author'],
                    cover_image_url: null,
                    // No min_condition → tests the false branch of {item.min_condition && ...}
                },
            ],
        });

        renderWithProviders(<PublicProfile />);
        expect(await screen.findByText('Flat Wanted Book')).toBeInTheDocument();
    });

    it('recovers from corrupt localStorage data in loadStoredWishlistPreferences catch block', async () => {
        useParams.mockReturnValue({ id: 'user-1' });
        useAuth.mockReturnValue({ isAuthenticated: true, user: { id: 'user-1' } });

        // Store corrupt (non-JSON) data in localStorage — causes JSON.parse to throw
        localStorage.setItem('wishlist-preferences:user-1', '{corrupt:json');

        users.getPublicProfile.mockResolvedValue({
            data: { id: 'user-1', username: 'reader', account_type: 'individual', is_verified: true, total_trades: 0 },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        users.getMe.mockResolvedValue({
            data: { id: 'user-1', full_name: '', address_line_1: '', city: '', state: '', zip_code: '', address_verification_status: 'unverified' },
        });
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });

        renderWithProviders(<PublicProfile />);

        // Component falls back to defaults when localStorage data is corrupt — form still renders
        expect(await screen.findByText('Wishlist Match Preferences')).toBeInTheDocument();
        expect(screen.getByLabelText('Minimum acceptable condition')).toHaveValue('any');

        localStorage.removeItem('wishlist-preferences:user-1');
    });

    it('continues silently when localStorage.setItem throws in saveWishlistPreferences', async () => {
        useParams.mockReturnValue({ id: 'user-1' });
        useAuth.mockReturnValue({ isAuthenticated: true, user: { id: 'user-1' } });

        users.getPublicProfile.mockResolvedValue({
            data: { id: 'user-1', username: 'reader', account_type: 'individual', is_verified: true, total_trades: 0 },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        users.getMe.mockResolvedValue({
            data: { id: 'user-1', full_name: '', address_line_1: '', city: '', state: '', zip_code: '', address_verification_status: 'unverified' },
        });
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        wishlist.update.mockResolvedValue({ data: {} });

        renderWithProviders(<PublicProfile />);
        await screen.findByText('Wishlist Match Preferences');

        // Make localStorage.setItem throw to trigger the catch block in saveWishlistPreferences
        const setItemSpy = vi.spyOn(localStorage, 'setItem').mockImplementationOnce(() => {
            throw new DOMException('QuotaExceededError');
        });

        await userEvent.click(screen.getByRole('button', { name: 'Save wishlist preferences' }));

        // Error is swallowed in catch block — success message still appears
        expect(await screen.findByText(/wishlist match defaults saved/i)).toBeInTheDocument();

        setItemSpy.mockRestore();
    });

    it('renders institution wanted book with flat structure and no optional fields (covers lines 378-395)', async () => {
        useParams.mockReturnValue({ id: 'institution-1' });
        useAuth.mockReturnValue({ isAuthenticated: false, user: null });

        users.getPublicProfile.mockResolvedValue({
            data: { id: 'institution-1', username: 'central-lib', account_type: 'institution', is_verified: true, total_trades: 5 },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        institutions.getWantedList.mockResolvedValue({
            data: [
                {
                    // No id field — covers item.id ?? i right side (line 380)
                    // No nested .book — item IS the book (covers item.book ?? item right side, line 378)
                    title: 'Flat Wanted Institution Book',
                    authors: ['Flat Inst Author'],
                    cover_image_url: null,
                    // No min_condition — covers {item.min_condition && ...} false branch (line 387)
                    // No quantity_needed — covers {item.quantity_needed && ...} false branch (line 392)
                },
            ],
        });

        renderWithProviders(<PublicProfile />);
        expect(await screen.findByText('Flat Wanted Institution Book')).toBeInTheDocument();
    });

    it('renders flat offeredBook (no nested .book) and item without condition (covers lines 415, 424)', async () => {
        useParams.mockReturnValue({ id: 'user-2' });
        useAuth.mockReturnValue({ isAuthenticated: false, user: null });

        users.getPublicProfile.mockResolvedValue({
            data: { id: 'user-2', username: 'reader2', account_type: 'individual', is_verified: true, total_trades: 1 },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        users.getUserOfferedBooks.mockResolvedValue({
            data: [
                {
                    id: 'flat-offered-1',
                    // No nested .book — item IS the book (covers item.book ?? item right side at line 415)
                    title: 'Flat Offered Title',
                    authors: ['Flat Author'],
                    cover_image_url: null,
                    // No condition field → covers {item.condition && ...} false branch at line 424
                },
            ],
        });

        renderWithProviders(<PublicProfile />);
        expect(await screen.findByText('Flat Offered Title')).toBeInTheDocument();
    });

    it('deselects a format preference in wishlist match prefs when clicked twice', async () => {
        useParams.mockReturnValue({ id: 'user-1' });
        useAuth.mockReturnValue({ isAuthenticated: true, user: { id: 'user-1' } });

        users.getPublicProfile.mockResolvedValue({
            data: { id: 'user-1', username: 'reader', account_type: 'individual', is_verified: true, total_trades: 3 },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        users.getMe.mockResolvedValue({
            data: { id: 'user-1', full_name: '', address_line_1: '', city: '', state: '', zip_code: '', address_verification_status: 'unverified' },
        });
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        wishlist.update.mockResolvedValue({ data: {} });

        renderWithProviders(<PublicProfile />);
        await screen.findByText('Wishlist Match Preferences');
        // Switch to custom to make format buttons appear
        await userEvent.selectOptions(screen.getByLabelText('Edition matching'), 'custom');
        // Click Hardcover to add it, then again to remove it (covers filter branch)
        await userEvent.click(screen.getByRole('button', { name: 'Hardcover' }));
        await userEvent.click(screen.getByRole('button', { name: 'Hardcover' }));
        await userEvent.click(screen.getByRole('button', { name: 'Save wishlist preferences' }));
        expect(wishlist.update).not.toHaveBeenCalled(); // no items to update (count=0, just saves defaults)
        // Verify the call path completed without error (success message appears)
        expect(await screen.findByText(/wishlist match defaults saved/i)).toBeInTheDocument();
    });
});
