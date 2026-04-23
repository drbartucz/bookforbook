import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import TradeDetail from './TradeDetail.jsx';

vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual('react-router-dom');
    return {
        ...actual,
        useParams: vi.fn(() => ({ id: 'trade-1' })),
    };
});

vi.mock('../services/api.js', () => ({
    trades: {
        getDetail: vi.fn(),
        getMessages: vi.fn(),
        sendMessage: vi.fn(),
        markShipped: vi.fn(),
        markReceived: vi.fn(),
        rate: vi.fn(),
    },
}));

vi.mock('../hooks/useAuth.js', () => ({
    default: vi.fn(),
}));

import { trades } from '../services/api.js';
import useAuth from '../hooks/useAuth.js';

describe('TradeDetail page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        useAuth.mockReturnValue({
            user: { id: 'user-1', username: 'bart0605' },
        });
    });

    it('renders trade books from the current API shape and sends a message', async () => {
        trades.getDetail.mockResolvedValue({
            data: {
                id: 'trade-1',
                status: 'confirmed',
                created_at: '2026-04-20T12:00:00Z',
                shipments: [
                    {
                        sender: { id: 'user-1', username: 'bart0605' },
                        receiver: { id: 'user-2', username: 'alice' },
                        status: 'pending',
                        user_book: {
                            condition: 'good',
                            book: {
                                id: 'book-1',
                                title: 'Kindred',
                                authors: ['Octavia E. Butler'],
                                cover_image_url: 'https://example.com/kindred.jpg',
                            },
                        },
                    },
                    {
                        sender: { id: 'user-2', username: 'alice' },
                        receiver: { id: 'user-1', username: 'bart0605' },
                        status: 'pending',
                        user_book: {
                            condition: 'very_good',
                            book: {
                                id: 'book-2',
                                title: 'The Left Hand of Darkness',
                                authors: ['Ursula K. Le Guin'],
                                cover_image_url: 'https://example.com/lefthand.jpg',
                            },
                        },
                    },
                ],
                partner_addresses: {
                    'user-2': {
                        full_name: 'Alice Reader',
                        address_line_1: '123 Main St',
                        address_line_2: '',
                        city: 'Denver',
                        state: 'CO',
                        zip_code: '80202',
                    },
                },
            },
        });
        trades.getMessages.mockResolvedValue({ data: [] });
        trades.sendMessage.mockResolvedValue({ data: {} });

        renderWithProviders(<TradeDetail />);

        expect(await screen.findByText('Kindred')).toBeInTheDocument();
        expect(screen.getByText('Octavia E. Butler')).toBeInTheDocument();
        expect(screen.getByText('The Left Hand of Darkness')).toBeInTheDocument();
        expect(screen.getByText('Ursula K. Le Guin')).toBeInTheDocument();
        expect(screen.getByAltText('Kindred')).toHaveAttribute('src', 'https://example.com/kindred.jpg');
        expect(screen.getByAltText('The Left Hand of Darkness')).toHaveAttribute('src', 'https://example.com/lefthand.jpg');

        await userEvent.type(screen.getByPlaceholderText('Type a message...'), 'Ready to ship soon');
        expect(screen.getByText('18/1000')).toBeInTheDocument();
        expect(screen.getByPlaceholderText('Type a message...')).toHaveAttribute('maxLength', '1000');

        await userEvent.click(screen.getByRole('button', { name: 'Send message' }));
        expect(screen.getByText('0/1000')).toBeInTheDocument();

        await waitFor(() => {
            expect(trades.sendMessage).toHaveBeenCalledWith('trade-1', {
                content: 'Ready to ship soon',
                message_type: 'general',
            });
        });
    });
});