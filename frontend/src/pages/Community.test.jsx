import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Community from './Community.jsx';

vi.mock('../services/api.js', () => ({
    community: {
        list: vi.fn(),
    },
}));

import { community } from '../services/api.js';

const MOCK_USERS = [
    {
        id: 'user-1',
        username: 'toptrader',
        account_type: 'individual',
        karma: 20,
        total_trades: 10,
        gifts_given_count: 5,
        avg_recent_rating: '4.80',
        giver_badge: 'top_10',
        trader_badge: 'top_10',
        created_at: '2024-01-15T00:00:00Z',
    },
    {
        id: 'user-2',
        username: 'bookworm42',
        account_type: 'individual',
        karma: 4,
        total_trades: 2,
        gifts_given_count: 1,
        avg_recent_rating: null,
        giver_badge: null,
        trader_badge: null,
        created_at: '2025-06-01T00:00:00Z',
    },
];

function mockListResponse(users = MOCK_USERS, count = null) {
    return {
        data: {
            count: count ?? users.length,
            next: null,
            previous: null,
            results: users,
        },
    };
}

describe('Community page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders page heading and subtitle', async () => {
        community.list.mockResolvedValue(mockListResponse([]));
        renderWithProviders(<Community />);
        expect(screen.getByText('Community')).toBeTruthy();
        expect(screen.getByText(/Discover active traders/i)).toBeTruthy();
    });

    it('shows loading spinner initially', () => {
        community.list.mockImplementation(() => new Promise(() => {}));
        renderWithProviders(<Community />);
        expect(document.querySelector('[class*="spinner"], [data-testid="spinner"], svg')).toBeTruthy();
    });

    it('renders user cards with usernames', async () => {
        community.list.mockResolvedValue(mockListResponse());
        renderWithProviders(<Community />);
        await waitFor(() => {
            expect(screen.getByText('@toptrader')).toBeTruthy();
            expect(screen.getByText('@bookworm42')).toBeTruthy();
        });
    });

    it('renders karma score with icon', async () => {
        community.list.mockResolvedValue(mockListResponse());
        renderWithProviders(<Community />);
        await waitFor(() => {
            expect(screen.getByText('20')).toBeTruthy();
        });
    });

    it('renders giver and trader badge chips for top user', async () => {
        community.list.mockResolvedValue(mockListResponse());
        renderWithProviders(<Community />);
        await waitFor(() => {
            expect(screen.getByText('Top 10% Giver')).toBeTruthy();
            expect(screen.getByText('Top 10% Trader')).toBeTruthy();
        });
    });

    it('renders total_trades and avg_recent_rating in stats', async () => {
        community.list.mockResolvedValue(mockListResponse());
        renderWithProviders(<Community />);
        await waitFor(() => {
            expect(screen.getByText('10 trades')).toBeTruthy();
            expect(screen.getByText('4.8 ★')).toBeTruthy();
        });
    });

    it('renders member year', async () => {
        community.list.mockResolvedValue(mockListResponse());
        renderWithProviders(<Community />);
        await waitFor(() => {
            expect(screen.getByText('Since 2024')).toBeTruthy();
        });
    });

    it('shows empty state when no users returned', async () => {
        community.list.mockResolvedValue(mockListResponse([]));
        renderWithProviders(<Community />);
        await waitFor(() => {
            expect(screen.getByText(/No users found/i)).toBeTruthy();
        });
    });

    it('renders sort dropdown with Karma as default', async () => {
        community.list.mockResolvedValue(mockListResponse([]));
        renderWithProviders(<Community />);
        const select = await screen.findByLabelText('Sort by');
        expect(select.value).toBe('-karma_score');
    });

    it('renders badge filter buttons', async () => {
        community.list.mockResolvedValue(mockListResponse([]));
        renderWithProviders(<Community />);
        await waitFor(() => {
            expect(screen.getByText('All')).toBeTruthy();
            expect(screen.getByText('Top Givers')).toBeTruthy();
            expect(screen.getByText('Top Traders')).toBeTruthy();
        });
    });

    it('renders has-books toggle', async () => {
        community.list.mockResolvedValue(mockListResponse([]));
        renderWithProviders(<Community />);
        await waitFor(() => {
            expect(screen.getByText(/Has books available/i)).toBeTruthy();
        });
    });

    it('renders search input', async () => {
        community.list.mockResolvedValue(mockListResponse([]));
        renderWithProviders(<Community />);
        expect(screen.getByPlaceholderText(/Search by username/i)).toBeTruthy();
    });

    it('calls api with search param after submitting search form', async () => {
        community.list.mockResolvedValue(mockListResponse([]));
        renderWithProviders(<Community />);
        const input = screen.getByPlaceholderText(/Search by username/i);
        await userEvent.type(input, 'alice');
        const searchBtn = screen.getByRole('button', { name: /search/i });
        await userEvent.click(searchBtn);
        await waitFor(() => {
            const lastCall = community.list.mock.calls[community.list.mock.calls.length - 1][0];
            expect(lastCall.search).toBe('alice');
        });
    });

    it('shows error state on api failure', async () => {
        community.list.mockRejectedValue(new Error('Network error'));
        renderWithProviders(<Community />);
        await waitFor(() => {
            expect(
                screen.queryByText(/error/i) ||
                document.querySelector('[class*="error"]')
            ).toBeTruthy();
        });
    });
});
