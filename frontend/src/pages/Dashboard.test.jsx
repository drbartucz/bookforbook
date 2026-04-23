import React from 'react';
import { screen } from '@testing-library/react';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Dashboard from './Dashboard.jsx';

vi.mock('../services/api.js', () => ({
    users: {
        getMe: vi.fn(),
    },
    matches: {
        list: vi.fn(),
    },
    proposals: {
        list: vi.fn(),
    },
    trades: {
        list: vi.fn(),
    },
}));

vi.mock('../hooks/useAuth.js', () => ({
    default: vi.fn(),
}));

import { matches, proposals, trades, users } from '../services/api.js';
import useAuth from '../hooks/useAuth.js';

describe('Dashboard page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders summary counts and recent activity from API responses', async () => {
        useAuth.mockReturnValue({
            user: { username: 'fallback-user' },
        });

        users.getMe.mockResolvedValue({
            data: { username: 'alice', total_trades: 7 },
        });
        matches.list.mockResolvedValue({
            data: {
                count: 2,
                results: [
                    {
                        id: 'match-1',
                        partner: { username: 'bob' },
                        your_book: { book: { title: 'Sapiens' } },
                    },
                ],
            },
        });
        proposals.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'proposal-1',
                        proposer: { username: 'carol' },
                        offered_book: { book: { title: 'Code Complete' } },
                    },
                ],
            },
        });
        trades.list.mockResolvedValue({
            data: {
                count: 3,
                results: [
                    {
                        id: 'trade-1',
                        status: 'active',
                        initiator_book: { book: { title: 'The Pragmatic Programmer' } },
                    },
                ],
            },
        });

        renderWithProviders(<Dashboard />);

        expect(await screen.findByText('Welcome back, alice!')).toBeInTheDocument();
        expect(screen.getByText('Pending Matches')).toBeInTheDocument();
        expect(screen.getByText('Pending Proposals')).toBeInTheDocument();
        expect(screen.getAllByText('Active Trades')).toHaveLength(2);
        expect(screen.getByText('New Matches')).toBeInTheDocument();
        expect(screen.getByText('Incoming Proposals')).toBeInTheDocument();
        expect(screen.getByText('Active Trades', { selector: 'h2' })).toBeInTheDocument();
        expect(screen.getByText('Sapiens')).toBeInTheDocument();
        expect(screen.getByText('Code Complete')).toBeInTheDocument();
        expect(screen.getByText('The Pragmatic Programmer')).toBeInTheDocument();
    });

    it('renders empty activity state when there are no recent items', async () => {
        useAuth.mockReturnValue({
            user: { username: 'alice' },
        });

        users.getMe.mockResolvedValue({ data: { username: 'alice', total_trades: 0 } });
        matches.list.mockResolvedValue({ data: { count: 0, results: [] } });
        proposals.list.mockResolvedValue({ data: { count: 0, results: [] } });
        trades.list.mockResolvedValue({ data: { count: 0, results: [] } });

        renderWithProviders(<Dashboard />);

        expect(await screen.findByText('No activity yet')).toBeInTheDocument();
        expect(screen.getByText('Add books to your have-list and wishlist to start getting matches.')).toBeInTheDocument();
    });
});
