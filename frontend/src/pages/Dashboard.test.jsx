import React from 'react';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Dashboard from './Dashboard.jsx';

vi.mock('../services/api.js', () => ({
    users: {
        getMe: vi.fn(),
    },
    matches: {
        list: vi.fn(),
        reverseDiscovery: vi.fn(),
    },
    proposals: {
        list: vi.fn(),
    },
    trades: {
        list: vi.fn(),
    },
    myBooks: {
        list: vi.fn(),
    },
    wishlist: {
        list: vi.fn(),
    },
}));

vi.mock('../hooks/useAuth.js', () => ({
    default: vi.fn(),
}));

import { matches, myBooks, proposals, trades, users, wishlist } from '../services/api.js';
import useAuth from '../hooks/useAuth.js';
import { ActivityItem } from './Dashboard.jsx';

// Reusable mock setup used by most tests. Returns plain arrays for matches,
// proposals, and trades — which is the actual shape the backend produces.
function setupDefaultMocks({
    matchesList = [],
    proposalsList = [],
    tradesList = [],
    myBooksCount = 0,
    wishlistCount = 0,
    discoveryList = [],
    totalTrades = 0,
    username = 'alice',
} = {}) {
    useAuth.mockReturnValue({ user: { username } });
    users.getMe.mockResolvedValue({ data: { username, total_trades: totalTrades } });
    matches.list.mockResolvedValue({ data: matchesList });
    matches.reverseDiscovery.mockResolvedValue({ data: discoveryList });
    proposals.list.mockResolvedValue({ data: proposalsList });
    trades.list.mockResolvedValue({ data: tradesList });
    myBooks.list.mockResolvedValue({ data: { count: myBooksCount, results: [] } });
    wishlist.list.mockResolvedValue({ data: { count: wishlistCount, results: [] } });
}

describe('Dashboard page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders all seven card labels when data loads', async () => {
        setupDefaultMocks();
        renderWithProviders(<Dashboard />);

        // Wait for content inside the loading gate (cards are hidden while isLoading)
        await screen.findByText('Proposed Matches');
        expect(screen.getByText('Potential Partners')).toBeInTheDocument();
        expect(screen.getByText('Pending Proposals')).toBeInTheDocument();
        // "Active Trades" appears in both the card label and the activity section heading
        expect(screen.getAllByText('Active Trades').length).toBeGreaterThanOrEqual(1);
        expect(screen.getByText('Total Trades')).toBeInTheDocument();
        expect(screen.getByText('Books Offered')).toBeInTheDocument();
        expect(screen.getByText('Books Wanted')).toBeInTheDocument();
    });

    it('shows correct counts from plain-array API responses (real backend shape)', async () => {
        setupDefaultMocks({
            matchesList: [
                { id: 'm1', partner: { username: 'bob' }, your_book: { book: { title: 'Sapiens' } } },
                { id: 'm2', partner: { username: 'carol' }, your_book: { book: { title: 'Dune' } } },
            ],
            proposalsList: [
                { id: 'p1', proposer: { username: 'carol' }, offered_book: { book: { title: 'Code Complete' } } },
            ],
            tradesList: [
                { id: 't1', status: 'confirmed', initiator_book: { book: { title: 'The Pragmatic Programmer' } } },
                { id: 't2', status: 'shipping', initiator_book: { book: { title: 'Clean Code' } } },
                { id: 't3', status: 'one_received', initiator_book: { book: { title: 'Refactoring' } } },
            ],
            discoveryList: [{ id: 'u1' }, { id: 'u2' }, { id: 'u3' }, { id: 'u4' }],
            myBooksCount: 5,
            wishlistCount: 8,
            totalTrades: 7,
        });

        renderWithProviders(<Dashboard />);

        // Wait for cards to render (they are inside the loading gate)
        await screen.findByText('Proposed Matches');

        // Each count value should appear exactly once as a standalone number in the card
        expect(screen.getByText('2')).toBeInTheDocument();  // Proposed Matches
        expect(screen.getByText('4')).toBeInTheDocument();  // Potential Partners
        expect(screen.getByText('1')).toBeInTheDocument();  // Pending Proposals
        expect(screen.getByText('3')).toBeInTheDocument();  // Active Trades
        expect(screen.getByText('7')).toBeInTheDocument();  // Total Trades
        expect(screen.getByText('5')).toBeInTheDocument();  // Books Offered
        expect(screen.getByText('8')).toBeInTheDocument();  // Books Wanted
    });

    it('renders activity feed items from plain-array responses', async () => {
        setupDefaultMocks({
            matchesList: [
                { id: 'm1', partner: { username: 'bob' }, your_book: { book: { title: 'Sapiens' } } },
            ],
            proposalsList: [
                { id: 'p1', proposer: { username: 'carol' }, offered_book: { book: { title: 'Code Complete' } } },
            ],
            tradesList: [
                { id: 't1', status: 'confirmed', initiator_book: { book: { title: 'The Pragmatic Programmer' } } },
            ],
        });

        renderWithProviders(<Dashboard />);

        await screen.findByText('Sapiens');
        expect(screen.getByText('Code Complete')).toBeInTheDocument();
        expect(screen.getByText('The Pragmatic Programmer')).toBeInTheDocument();
        expect(screen.getByText('New Matches')).toBeInTheDocument();
        expect(screen.getByText('Incoming Proposals')).toBeInTheDocument();
    });

    it('renders correct counts from paginated-envelope API responses (legacy shape)', async () => {
        // Verify parsePaginatedResponse also handles { count, results } objects
        useAuth.mockReturnValue({ user: { username: 'alice' } });
        users.getMe.mockResolvedValue({ data: { username: 'alice', total_trades: 7 } });
        matches.list.mockResolvedValue({
            data: { count: 2, results: [{ id: 'm1', partner: { username: 'bob' }, your_book: { book: { title: 'Sapiens' } } }] },
        });
        matches.reverseDiscovery.mockResolvedValue({ data: [] });
        proposals.list.mockResolvedValue({
            data: { count: 1, results: [{ id: 'p1', proposer: { username: 'carol' }, offered_book: { book: { title: 'Code Complete' } } }] },
        });
        trades.list.mockResolvedValue({
            data: { count: 3, results: [{ id: 't1', status: 'confirmed', initiator_book: { book: { title: 'The Pragmatic Programmer' } } }] },
        });
        myBooks.list.mockResolvedValue({ data: { count: 5, results: [] } });
        wishlist.list.mockResolvedValue({ data: { count: 8, results: [] } });

        renderWithProviders(<Dashboard />);

        await screen.findByText('Proposed Matches');
        expect(screen.getByText('2')).toBeInTheDocument();  // Proposed Matches
        expect(screen.getByText('1')).toBeInTheDocument();  // Pending Proposals
        expect(screen.getByText('3')).toBeInTheDocument();  // Active Trades
        expect(screen.getByText('7')).toBeInTheDocument();  // Total Trades
    });

    it('shows all zeros when there is no data', async () => {
        setupDefaultMocks();
        renderWithProviders(<Dashboard />);

        await screen.findByText('Proposed Matches');
        const zeros = screen.getAllByText('0');
        // 6 numeric cards show 0 (all except Total Trades which also shows 0 = 7 total)
        expect(zeros.length).toBeGreaterThanOrEqual(6);
    });

    it('renders empty activity state when there are no recent items', async () => {
        setupDefaultMocks({ username: 'alice' });
        renderWithProviders(<Dashboard />);

        expect(await screen.findByText('No activity yet')).toBeInTheDocument();
        expect(screen.getByText('Add books to your have-list and wishlist to start getting matches.')).toBeInTheDocument();
    });

    it('Proposed Matches card links to /matches', async () => {
        setupDefaultMocks();
        renderWithProviders(<Dashboard />);

        // findByText waits for the loading gate to clear
        const label = await screen.findByText('Proposed Matches');
        expect(label.closest('a')).toHaveAttribute('href', '/matches');
    });

    it('Potential Partners card links to /discovery', async () => {
        setupDefaultMocks();
        renderWithProviders(<Dashboard />);

        const label = await screen.findByText('Potential Partners');
        expect(label.closest('a')).toHaveAttribute('href', '/discovery');
    });

    it('Pending Proposals card links to /proposals', async () => {
        setupDefaultMocks();
        renderWithProviders(<Dashboard />);

        const label = await screen.findByText('Pending Proposals');
        expect(label.closest('a')).toHaveAttribute('href', '/proposals');
    });

    it('Active Trades card links to /trades', async () => {
        setupDefaultMocks();
        renderWithProviders(<Dashboard />);

        // Multiple elements match "Active Trades" (card + activity heading) — the first is the card
        await screen.findByText('Proposed Matches'); // wait for loading gate
        const tradeCard = screen.getAllByText('Active Trades')[0].closest('a');
        expect(tradeCard).toHaveAttribute('href', '/trades');
    });

    it('Books Offered card links to /my-books', async () => {
        setupDefaultMocks();
        renderWithProviders(<Dashboard />);

        const label = await screen.findByText('Books Offered');
        expect(label.closest('a')).toHaveAttribute('href', '/my-books');
    });

    it('Books Wanted card links to /wishlist', async () => {
        setupDefaultMocks();
        renderWithProviders(<Dashboard />);

        const label = await screen.findByText('Books Wanted');
        expect(label.closest('a')).toHaveAttribute('href', '/wishlist');
    });

    it('Total Trades card is not a link', async () => {
        setupDefaultMocks();
        renderWithProviders(<Dashboard />);

        const label = await screen.findByText('Total Trades');
        expect(label.closest('a')).toBeNull();
    });

    it('welcome message uses username from getMe response, falling back to auth store', async () => {
        useAuth.mockReturnValue({ user: { username: 'fallback-user' } });
        users.getMe.mockResolvedValue({ data: { username: 'alice', total_trades: 0 } });
        matches.list.mockResolvedValue({ data: [] });
        matches.reverseDiscovery.mockResolvedValue({ data: [] });
        proposals.list.mockResolvedValue({ data: [] });
        trades.list.mockResolvedValue({ data: [] });
        myBooks.list.mockResolvedValue({ data: { count: 0, results: [] } });
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });

        renderWithProviders(<Dashboard />);

        // getMe takes priority over the auth store user
        expect(await screen.findByText('Welcome back, alice!')).toBeInTheDocument();
    });
});

describe('ActivityItem fallback branches', () => {
    it('renders fallback title, empty subtitle, root link, and gray badge for an unknown type', () => {
        renderWithProviders(<ActivityItem type="unknown" item={{ id: 'x' }} />);
        expect(screen.getByText('Activity')).toBeInTheDocument();
        expect(screen.getByText('unknown')).toBeInTheDocument();
    });

    it('renders match type with partner username', () => {
        renderWithProviders(
            <ActivityItem type="match" item={{ id: 'm1', partner: { username: 'bob' }, your_book: { book: { title: 'Dune' } } }} />
        );
        expect(screen.getByText('Dune')).toBeInTheDocument();
        expect(screen.getByText('Partner: bob')).toBeInTheDocument();
        expect(screen.getByText('Match')).toBeInTheDocument();
        expect(screen.getByRole('link')).toHaveAttribute('href', '/matches');
    });

    it('renders proposal type with proposer username', () => {
        renderWithProviders(
            <ActivityItem type="proposal" item={{ id: 'p1', proposer: { username: 'carol' }, offered_book: { book: { title: 'Clean Code' } } }} />
        );
        expect(screen.getByText('Clean Code')).toBeInTheDocument();
        expect(screen.getByText('From: carol')).toBeInTheDocument();
        expect(screen.getByText('Proposal')).toBeInTheDocument();
        expect(screen.getByRole('link')).toHaveAttribute('href', '/proposals');
    });

    it('renders trade type linking to the specific trade', () => {
        renderWithProviders(
            <ActivityItem type="trade" item={{ id: 'trade-abc', status: 'shipping', initiator_book: { book: { title: 'Refactoring' } } }} />
        );
        expect(screen.getByText('Refactoring')).toBeInTheDocument();
        expect(screen.getByText('Status: shipping')).toBeInTheDocument();
        expect(screen.getByText('Trade')).toBeInTheDocument();
        expect(screen.getByRole('link')).toHaveAttribute('href', '/trades/trade-abc');
    });

    it('renders generic fallback title when book data is missing', () => {
        renderWithProviders(<ActivityItem type="match" item={{ id: 'm1' }} />);
        expect(screen.getByText('Book match')).toBeInTheDocument();
        expect(screen.getByText('Partner: Unknown')).toBeInTheDocument();
    });
});
