import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Institutions from './Institutions.jsx';

vi.mock('../services/api.js', () => ({
    institutions: {
        list: vi.fn(),
    },
}));

vi.mock('../hooks/useDebounce.js', () => ({
    default: vi.fn((value) => value),
}));

import { institutions } from '../services/api.js';

describe('Institutions page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders institution cards from API response', async () => {
        institutions.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'inst-1',
                        display_name: 'Portland Public Library',
                        institution_type: 'library',
                        is_verified: true,
                        location: 'Portland, OR',
                        bio: 'Community-focused public library system.',
                        total_trades: 12,
                        wanted_count: 5,
                        avg_recent_rating: 4.8,
                    },
                ],
            },
        });

        renderWithProviders(<Institutions />);

        expect(await screen.findByText('Portland Public Library')).toBeInTheDocument();
        expect(screen.getByText('Verified')).toBeInTheDocument();
        expect(screen.getByText('library')).toBeInTheDocument();
        expect(screen.getByText('Portland, OR')).toBeInTheDocument();
        expect(screen.getByText('12 trades')).toBeInTheDocument();
        expect(screen.getByText('5 books wanted')).toBeInTheDocument();
        expect(screen.getByText('4.8 ★')).toBeInTheDocument();
        expect(screen.getByRole('link', { name: 'View Profile →' })).toHaveAttribute('href', '/profile/inst-1');
    });

    it('shows error state when API fails', async () => {
        institutions.list.mockRejectedValue(new Error('Server error'));
        renderWithProviders(<Institutions />);
        // isError=true → renders ErrorMessage (covers line 93)
        expect(await screen.findByText(/server error/i)).toBeInTheDocument();
    });

    it('shows plural "institutions" count when count > 1 (covers false branch of === 1 ternary)', async () => {
        institutions.list.mockResolvedValue({
            data: {
                count: 3,
                results: [
                    {
                        id: 'inst-a',
                        display_name: 'Library Alpha',
                        institution_type: 'library',
                        is_verified: true,
                        location: 'Seattle, WA',
                        total_trades: 5,
                        wanted_count: 2,
                        avg_recent_rating: 4.5,
                    },
                    {
                        id: 'inst-b',
                        // No display_name — falls back to institution.name (covers middle ?? branch)
                        name: 'Bookstore Beta',
                        institution_type: 'bookstore',
                        is_verified: false,
                        location: null,
                        total_trades: 3,
                        wanted_count: 1,
                        avg_recent_rating: null,
                    },
                    {
                        id: 'inst-c',
                        institution_type: 'library',
                        is_verified: false,
                        // Has nested user with username (covers institution.user ?? left branch)
                        user: {
                            id: 'user-inst',
                            username: 'central-lib',
                        },
                        // No display_name, no name → uses user.username (covers ?? right branch)
                        total_trades: 0,
                        wanted_count: 0,
                        avg_recent_rating: null,
                    },
                ],
            },
        });

        renderWithProviders(<Institutions />);

        expect(await screen.findByText('Library Alpha')).toBeInTheDocument();
        // Count > 1 → plural 's'
        expect(await screen.findByText('3 institutions')).toBeInTheDocument();
        // Name fallback (no display_name)
        expect(screen.getByText('Bookstore Beta')).toBeInTheDocument();
        // Username from nested user object (no display_name or name)
        expect(screen.getByText('central-lib')).toBeInTheDocument();
    });

    it('shows count as 0 when API response omits count field (covers data?.count ?? 0 right branch)', async () => {
        institutions.list.mockResolvedValue({
            data: {
                // No count field — triggers data?.count ?? 0 right side (line 106)
                results: [
                    {
                        id: 'inst-no-count',
                        display_name: 'No Count Library',
                        institution_type: 'library',
                        is_verified: true,
                        location: 'Denver, CO',
                        total_trades: 1,
                        wanted_count: 0,
                        avg_recent_rating: null,
                    },
                ],
            },
        });

        renderWithProviders(<Institutions />);
        // data?.count is undefined → ?? 0 fires; then 0 !== 1 → 's' appended
        expect(await screen.findByText('No Count Library')).toBeInTheDocument();
        expect(screen.getByText('0 institutions')).toBeInTheDocument();
    });

    it('uses institution.id when institution.user has no id field (covers user.id ?? institution.id right branch)', async () => {
        institutions.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'inst-fallback-id',
                        display_name: 'User No ID Lib',
                        institution_type: 'library',
                        is_verified: false,
                        total_trades: 0,
                        wanted_count: 0,
                        avg_recent_rating: null,
                        // user exists but has no id — covers user.id ?? institution.id right side (line 122)
                        user: { username: 'no-id-user' },
                    },
                ],
            },
        });

        renderWithProviders(<Institutions />);
        expect(await screen.findByText('User No ID Lib')).toBeInTheDocument();
        // Profile link uses institution.id as fallback
        expect(screen.getByRole('link', { name: 'View Profile →' })).toHaveAttribute('href', '/profile/inst-fallback-id');
    });

    it('sends search and type filters to the API', async () => {
        institutions.list.mockResolvedValue({ data: { count: 0, results: [] } });

        renderWithProviders(<Institutions />);

        await userEvent.type(screen.getByLabelText('Search institutions'), 'portland');
        await userEvent.selectOptions(screen.getByLabelText('Filter by type'), 'library');

        await waitFor(() => {
            expect(institutions.list).toHaveBeenLastCalledWith(
                expect.objectContaining({
                    page: 1,
                    page_size: 20,
                    search: 'portland',
                    institution_type: 'library',
                })
            );
        });
    });
});
