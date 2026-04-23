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
