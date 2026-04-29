import React from 'react';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Trades from './Trades.jsx';

vi.mock('../services/api.js', () => ({
    trades: {
        list: vi.fn(),
    },
}));

vi.mock('../hooks/useAuth.js', () => ({
    default: vi.fn(() => ({ user: { id: 'user-1', username: 'bart0605' } })),
}));

import { trades } from '../services/api.js';

describe('Trades page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders trade books from the current API shape', async () => {
        trades.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'trade-1',
                        status: 'confirmed',
                        created_at: '2026-04-20T12:00:00Z',
                        shipments: [
                            {
                                sender: { id: 'user-1', username: 'bart0605' },
                                receiver: { id: 'user-2', username: 'bob' },
                                status: 'pending',
                                user_book: {
                                    condition: 'good',
                                    book: {
                                        id: 'book-1',
                                        title: 'Parable of the Sower',
                                        authors: ['Octavia E. Butler'],
                                        cover_image_url: 'https://example.com/sower.jpg',
                                    },
                                },
                            },
                            {
                                sender: { id: 'user-2', username: 'bob' },
                                receiver: { id: 'user-1', username: 'bart0605' },
                                status: 'pending',
                                user_book: {
                                    condition: 'very_good',
                                    book: {
                                        id: 'book-2',
                                        title: 'A Wizard of Earthsea',
                                        authors: ['Ursula K. Le Guin'],
                                        cover_image_url: 'https://example.com/earthsea.jpg',
                                    },
                                },
                            },
                        ],
                    },
                ],
            },
        });

        renderWithProviders(<Trades />);

        expect(await screen.findByText('Parable of the Sower')).toBeInTheDocument();
        expect(screen.getByText('Octavia E. Butler')).toBeInTheDocument();
        expect(screen.getByText('A Wizard of Earthsea')).toBeInTheDocument();
        expect(screen.getByText('Ursula K. Le Guin')).toBeInTheDocument();
        expect(screen.getByAltText('Parable of the Sower')).toHaveAttribute(
            'src',
            'https://example.com/sower.jpg'
        );
        expect(screen.getByAltText('A Wizard of Earthsea')).toHaveAttribute(
            'src',
            'https://example.com/earthsea.jpg'
        );
        expect(screen.getByText('@bob')).toBeInTheDocument();
    });

    it('shows loading spinner while fetching', () => {
        trades.list.mockReturnValue(new Promise(() => { }));
        renderWithProviders(<Trades />);
        expect(document.querySelector('[class*="spinner"]') || document.querySelector('[class*="loading"]') || screen.queryByText(/loading/i)).toBeTruthy();
    });

    it('shows error message when trade fetch fails', async () => {
        trades.list.mockRejectedValue(new Error('Network error'));
        renderWithProviders(<Trades />);
        expect(await screen.findByText(/network error/i)).toBeInTheDocument();
    });

    it('shows empty state with link to matches when no trades found', async () => {
        trades.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Trades />);
        expect(await screen.findByText(/no trades found/i)).toBeInTheDocument();
        expect(screen.getByRole('link', { name: /view matches/i })).toBeInTheDocument();
    });

    it('renders trades from paginated API response and handles no cover/author', async () => {
        trades.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'trade-arr-1',
                        status: 'unknown_custom_status',  // not in TRADE_STATUS_CONFIG
                        created_at: '2026-04-20T12:00:00Z',
                        shipments: [
                            {
                                sender: { id: 'user-1', username: 'bart0605' },
                                receiver: { id: 'user-2', username: 'bob' },
                                status: 'pending',
                                user_book: {
                                    condition: 'good',
                                    book: {
                                        id: 'book-nc1',
                                        title: 'No Cover Book',
                                        authors: [],
                                        cover_image_url: null,
                                    },
                                },
                            },
                            {
                                sender: { id: 'user-2', username: 'bob' },
                                receiver: { id: 'user-1', username: 'bart0605' },
                                status: 'pending',
                                user_book: {
                                    condition: 'good',
                                    book: {
                                        id: 'book-nc2',
                                        title: 'Also No Cover',
                                        authors: [],
                                        cover_image_url: null,
                                    },
                                },
                            },
                        ],
                    },
                ],
            },
        });
        renderWithProviders(<Trades />);
        expect(await screen.findByText('No Cover Book')).toBeInTheDocument();
        expect(screen.getByText('Also No Cover')).toBeInTheDocument();
        // Unknown status falls back to raw status text
        expect(screen.getByText('unknown_custom_status')).toBeInTheDocument();
    });

    it('shows "Unknown" for both books when trade has no matching shipments for current user', async () => {
        trades.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'trade-no-match',
                        status: 'confirmed',
                        created_at: '2026-04-20T12:00:00Z',
                        shipments: [
                            // user-1 is not sender or receiver in any shipment
                            {
                                sender: { id: 'user-2', username: 'bob' },
                                receiver: { id: 'user-3', username: 'charlie' },
                                status: 'pending',
                                user_book: { condition: 'good', book: { id: 'bx', title: 'Someone Else Book', authors: [] } },
                            },
                        ],
                    },
                ],
            },
        });
        renderWithProviders(<Trades />);
        const unknowns = await screen.findAllByText('Unknown');
        // myBook?.title ?? 'Unknown' and theirBook?.title ?? 'Unknown'
        expect(unknowns.length).toBeGreaterThanOrEqual(2);
    });

    it('renders flat user_book (no nested .book property) using user_book directly', async () => {
        trades.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'trade-flat',
                        status: 'confirmed',
                        created_at: '2026-04-20T12:00:00Z',
                        shipments: [
                            {
                                sender: { id: 'user-1', username: 'bart0605' },
                                receiver: { id: 'user-2', username: 'bob' },
                                status: 'pending',
                                // user_book has no nested .book — flat structure
                                user_book: {
                                    id: 'flat-ub-1',
                                    title: 'Flat Sender Book',
                                    authors: ['Flat Author One'],
                                    cover_image_url: null,
                                },
                            },
                            {
                                sender: { id: 'user-2', username: 'bob' },
                                receiver: { id: 'user-1', username: 'bart0605' },
                                status: 'pending',
                                user_book: {
                                    id: 'flat-ub-2',
                                    title: 'Flat Receiver Book',
                                    authors: ['Flat Author Two'],
                                    cover_image_url: null,
                                },
                            },
                        ],
                    },
                ],
            },
        });
        renderWithProviders(<Trades />);
        // trade.myBook?.book is undefined → falls back to trade.myBook itself (covers ?? right side)
        expect(await screen.findByText('Flat Sender Book')).toBeInTheDocument();
        expect(screen.getByText('Flat Receiver Book')).toBeInTheDocument();
    });

    it('filters by status when tab is clicked', async () => {
        trades.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Trades />);
        const activeTab = await screen.findByRole('button', { name: /active/i });
        await userEvent.click(activeTab);
        expect(trades.list).toHaveBeenCalledWith(expect.objectContaining({ status: 'active' }));
    });
});