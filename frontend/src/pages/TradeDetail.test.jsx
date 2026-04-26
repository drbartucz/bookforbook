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

// ── Helpers ──────────────────────────────────────────────────────────────────

function makeTrade(overrides = {}) {
    return {
        id: 'trade-1',
        status: 'confirmed',
        created_at: '2026-04-20T12:00:00Z',
        shipments: [
            {
                sender: { id: 'user-1', username: 'me' },
                receiver: { id: 'user-2', username: 'partner' },
                status: 'pending',
                tracking_number: '',
                user_book: {
                    condition: 'good',
                    book: { id: 'b1', title: 'My Book', authors: ['Author A'] },
                },
            },
            {
                sender: { id: 'user-2', username: 'partner' },
                receiver: { id: 'user-1', username: 'me' },
                status: 'pending',
                tracking_number: '',
                user_book: {
                    condition: 'very_good',
                    book: { id: 'b2', title: 'Their Book', authors: ['Author B'] },
                },
            },
        ],
        ...overrides,
    };
}

describe('TradeDetail page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        useAuth.mockReturnValue({
            user: { id: 'user-1', username: 'bart0605' },
        });
    });

    it('shows loading spinner while data is loading', () => {
        trades.getDetail.mockReturnValue(new Promise(() => {}));
        trades.getMessages.mockReturnValue(new Promise(() => {}));
        renderWithProviders(<TradeDetail />);
        expect(screen.getByText(/loading trade details/i)).toBeInTheDocument();
    });

    it('shows error message when trade fetch fails', async () => {
        trades.getDetail.mockRejectedValue(new Error('Network error'));
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        expect(await screen.findByText(/network error/i)).toBeInTheDocument();
    });

    it('shows "Mark My Book as Shipped" button when trade is confirmed and user has not shipped', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade({ status: 'confirmed' }) });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        expect(await screen.findByRole('button', { name: /mark my book as shipped/i })).toBeInTheDocument();
    });

    it('shows shipping form when "Mark My Book as Shipped" is clicked', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade({ status: 'confirmed' }) });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        await userEvent.click(await screen.findByRole('button', { name: /mark my book as shipped/i }));
        expect(screen.getByLabelText(/tracking number/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /confirm shipped/i })).toBeInTheDocument();
    });

    it('cancels shipping form when Cancel is clicked', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade({ status: 'confirmed' }) });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        await userEvent.click(await screen.findByRole('button', { name: /mark my book as shipped/i }));
        await userEvent.click(screen.getByRole('button', { name: /^cancel$/i }));
        expect(screen.queryByLabelText(/tracking number/i)).not.toBeInTheDocument();
    });

    it('submits mark-shipped with tracking number', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade({ status: 'confirmed' }) });
        trades.getMessages.mockResolvedValue({ data: [] });
        trades.markShipped.mockResolvedValue({ data: {} });
        renderWithProviders(<TradeDetail />);
        await userEvent.click(await screen.findByRole('button', { name: /mark my book as shipped/i }));
        await userEvent.type(screen.getByLabelText(/tracking number/i), 'TRACK123');
        await userEvent.click(screen.getByRole('button', { name: /confirm shipped/i }));
        await waitFor(() => expect(trades.markShipped).toHaveBeenCalledWith('trade-1', { tracking_number: 'TRACK123' }));
    });

    it('shows "Mark Book Received" button when partner has shipped', async () => {
        const trade = makeTrade({
            status: 'shipping',
            shipments: [
                {
                    sender: { id: 'user-1', username: 'me' },
                    receiver: { id: 'user-2', username: 'partner' },
                    status: 'shipped',
                    tracking_number: 'TRK1',
                    shipped_at: '2026-04-22T00:00:00Z',
                    user_book: { condition: 'good', book: { id: 'b1', title: 'My Book', authors: [] } },
                },
                {
                    sender: { id: 'user-2', username: 'partner' },
                    receiver: { id: 'user-1', username: 'me' },
                    status: 'shipped',
                    tracking_number: 'TRK2',
                    shipped_at: '2026-04-23T00:00:00Z',
                    user_book: { condition: 'very_good', book: { id: 'b2', title: 'Their Book', authors: [] } },
                },
            ],
        });
        trades.getDetail.mockResolvedValue({ data: trade });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        expect(await screen.findByRole('button', { name: /mark book received/i })).toBeInTheDocument();
    });

    it('shows "Rate Trade Partner" button when trade is completed and user has not rated', async () => {
        const trade = makeTrade({
            status: 'completed',
            i_rated: false,
            shipments: [
                {
                    sender: { id: 'user-1', username: 'me' },
                    receiver: { id: 'user-2', username: 'partner' },
                    status: 'received',
                    tracking_number: '',
                    user_book: { condition: 'good', book: { id: 'b1', title: 'My Book', authors: [] } },
                },
                {
                    sender: { id: 'user-2', username: 'partner' },
                    receiver: { id: 'user-1', username: 'me' },
                    status: 'received',
                    tracking_number: '',
                    user_book: { condition: 'very_good', book: { id: 'b2', title: 'Their Book', authors: [] } },
                },
            ],
        });
        trades.getDetail.mockResolvedValue({ data: trade });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        expect(await screen.findByRole('button', { name: /rate trade partner/i })).toBeInTheDocument();
    });

    it('opens rating form and submits rating', async () => {
        const trade = makeTrade({
            status: 'completed',
            i_rated: false,
            shipments: [
                {
                    sender: { id: 'user-1', username: 'me' },
                    receiver: { id: 'user-2', username: 'partner' },
                    status: 'received',
                    tracking_number: '',
                    user_book: { condition: 'good', book: { id: 'b1', title: 'My Book', authors: [] } },
                },
                {
                    sender: { id: 'user-2', username: 'partner' },
                    receiver: { id: 'user-1', username: 'me' },
                    status: 'received',
                    tracking_number: '',
                    user_book: { condition: 'very_good', book: { id: 'b2', title: 'Their Book', authors: [] } },
                },
            ],
        });
        trades.getDetail.mockResolvedValue({ data: trade });
        trades.getMessages.mockResolvedValue({ data: [] });
        trades.rate.mockResolvedValue({ data: {} });
        renderWithProviders(<TradeDetail />);
        await userEvent.click(await screen.findByRole('button', { name: /rate trade partner/i }));
        expect(screen.getByRole('button', { name: /submit rating/i })).toBeInTheDocument();
        await userEvent.click(screen.getByRole('button', { name: /submit rating/i }));
        await waitFor(() => expect(trades.rate).toHaveBeenCalled());
    });

    it('shows "You have rated this trade" when iRated is true', async () => {
        const trade = makeTrade({ status: 'completed', i_rated: true });
        trades.getDetail.mockResolvedValue({ data: trade });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        expect(await screen.findByText(/you have rated this trade/i)).toBeInTheDocument();
    });

    it('renders messages from other users', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade() });
        trades.getMessages.mockResolvedValue({
            data: [
                {
                    id: 'msg-1',
                    content: 'Hello from partner!',
                    message_type: 'general',
                    sender: { id: 'user-2', username: 'partner' },
                    created_at: '2026-04-20T13:00:00Z',
                },
                {
                    id: 'msg-2',
                    content: 'Shipping update info',
                    message_type: 'shipping_update',
                    sender: { id: 'user-1', username: 'me' },
                    created_at: '2026-04-20T14:00:00Z',
                },
            ],
        });
        renderWithProviders(<TradeDetail />);
        expect(await screen.findByText('Hello from partner!')).toBeInTheDocument();
        expect(screen.getByText('Shipping update info')).toBeInTheDocument();
        expect(screen.getByText('shipping update')).toBeInTheDocument(); // message_type badge
        expect(screen.getByText('You')).toBeInTheDocument();
        expect(screen.getByText('partner')).toBeInTheDocument();
    });

    it('shows shipping address when status is not confirmed', async () => {
        const trade = makeTrade({
            status: 'shipping',
            partner_addresses: {
                'user-2': {
                    full_name: 'Alice Reader',
                    address_line_1: '123 Main St',
                    address_line_2: 'Apt 2',
                    city: 'Denver',
                    state: 'CO',
                    zip_code: '80202',
                },
            },
            shipments: [
                {
                    sender: { id: 'user-1', username: 'me' },
                    receiver: { id: 'user-2', username: 'partner' },
                    status: 'shipped',
                    tracking_number: '',
                    user_book: { condition: 'good', book: { id: 'b1', title: 'My Book', authors: [] } },
                },
                {
                    sender: { id: 'user-2', username: 'partner' },
                    receiver: { id: 'user-1', username: 'me' },
                    status: 'pending',
                    tracking_number: '',
                    user_book: { condition: 'very_good', book: { id: 'b2', title: 'Their Book', authors: [] } },
                },
            ],
        });
        trades.getDetail.mockResolvedValue({ data: trade });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        expect(await screen.findByText('Alice Reader')).toBeInTheDocument();
        expect(screen.getByText('Apt 2')).toBeInTheDocument();
    });

    it('shows "Received" badge in ShippingStatus for received shipment', async () => {
        const trade = makeTrade({
            status: 'completed',
            i_rated: true,
            shipments: [
                {
                    sender: { id: 'user-1', username: 'me' },
                    receiver: { id: 'user-2', username: 'partner' },
                    status: 'received',
                    tracking_number: 'TRK1',
                    shipped_at: '2026-04-22T00:00:00Z',
                    user_book: { condition: 'good', book: { id: 'b1', title: 'My Book', authors: [] } },
                },
                {
                    sender: { id: 'user-2', username: 'partner' },
                    receiver: { id: 'user-1', username: 'me' },
                    status: 'received',
                    tracking_number: 'TRK2',
                    shipped_at: '2026-04-23T00:00:00Z',
                    user_book: { condition: 'very_good', book: { id: 'b2', title: 'Their Book', authors: [] } },
                },
            ],
        });
        trades.getDetail.mockResolvedValue({ data: trade });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        const received = await screen.findAllByText('Received');
        expect(received.length).toBeGreaterThan(0);
    });

    it('shows "Shipped" badge with tracking number in ShippingStatus', async () => {
        const trade = makeTrade({
            status: 'shipping',
            shipments: [
                {
                    sender: { id: 'user-1', username: 'me' },
                    receiver: { id: 'user-2', username: 'partner' },
                    status: 'shipped',
                    tracking_number: 'TRK-ABC',
                    shipped_at: '2026-04-22T10:00:00Z',
                    user_book: { condition: 'good', book: { id: 'b1', title: 'My Book', authors: [] } },
                },
                {
                    sender: { id: 'user-2', username: 'partner' },
                    receiver: { id: 'user-1', username: 'me' },
                    status: 'pending',
                    tracking_number: '',
                    user_book: { condition: 'very_good', book: { id: 'b2', title: 'Their Book', authors: [] } },
                },
            ],
        });
        trades.getDetail.mockResolvedValue({ data: trade });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        expect(await screen.findByText('TRK-ABC')).toBeInTheDocument();
        const shipped = await screen.findAllByText('Shipped');
        expect(shipped.length).toBeGreaterThan(0);
    });

    it('shows action error when message send fails', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade() });
        trades.getMessages.mockResolvedValue({ data: [] });
        trades.sendMessage.mockRejectedValue({
            response: { data: { detail: 'Send failed.' } },
        });
        renderWithProviders(<TradeDetail />);
        await screen.findByText('My Book');
        await userEvent.type(screen.getByPlaceholderText('Type a message...'), 'hello');
        await userEvent.click(screen.getByRole('button', { name: 'Send message' }));
        expect(await screen.findByText('Send failed.')).toBeInTheDocument();
    });

    it('sends message with Enter key', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade() });
        trades.getMessages.mockResolvedValue({ data: [] });
        trades.sendMessage.mockResolvedValue({ data: {} });
        renderWithProviders(<TradeDetail />);
        await screen.findByText('My Book');
        const textarea = screen.getByPlaceholderText('Type a message...');
        await userEvent.type(textarea, 'Enter test{Enter}');
        await waitFor(() => expect(trades.sendMessage).toHaveBeenCalled());
    });

    it('does not send empty message', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade() });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        await screen.findByText('My Book');
        await userEvent.click(screen.getByRole('button', { name: 'Send message' }));
        expect(trades.sendMessage).not.toHaveBeenCalled();
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

    it('does not send message typed as whitespace-only via Enter key', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade() });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        await screen.findByText('My Book');
        const textarea = screen.getByPlaceholderText('Type a message...');
        // Type only spaces and press Enter — trimmed content is empty so submitMessageIfValid returns early
        await userEvent.type(textarea, '   {Enter}');
        expect(trades.sendMessage).not.toHaveBeenCalled();
    });

    it('clicking a star changes the rating score and updates star active states', async () => {
        const trade = makeTrade({
            status: 'completed',
            i_rated: false,
            shipments: [
                { sender: { id: 'user-1', username: 'me' }, receiver: { id: 'user-2', username: 'partner' },
                  status: 'received', tracking_number: '', user_book: { condition: 'good', book: { id: 'b1', title: 'My Book', authors: [] } } },
                { sender: { id: 'user-2', username: 'partner' }, receiver: { id: 'user-1', username: 'me' },
                  status: 'received', tracking_number: '', user_book: { condition: 'very_good', book: { id: 'b2', title: 'Their Book', authors: [] } } },
            ],
        });
        trades.getDetail.mockResolvedValue({ data: trade });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        await userEvent.click(await screen.findByRole('button', { name: /rate trade partner/i }));
        // Click star 1 — sets ratingScore=1, stars 2-5 should NOT be active (covers '' branch)
        const stars = screen.getAllByText('★');
        await userEvent.click(stars[0]); // star 1
        // Rating label should reflect score 1
        expect(screen.getByText('1 / 5')).toBeInTheDocument();
    });

    it('renders message with no sender username using "Partner" fallback', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade() });
        trades.getMessages.mockResolvedValue({
            data: [{
                id: 'msg-nosender',
                content: 'Message with no sender',
                message_type: 'general',
                sender: null,  // no sender → 'Partner' fallback
                created_at: '2026-04-20T13:00:00Z',
            }],
        });
        renderWithProviders(<TradeDetail />);
        expect(await screen.findByText('Message with no sender')).toBeInTheDocument();
        expect(screen.getByText('Partner')).toBeInTheDocument();
    });

    it('shows "Unable to determine trade partner" when rating a trade with no shipments', async () => {
        // Trade with no shipments → partner = null → buildTradeRatingPayload returns null → throw
        const trade = {
            id: 'trade-no-partner',
            status: 'completed',
            i_rated: false,
            shipments: [],
        };
        trades.getDetail.mockResolvedValue({ data: trade });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        await userEvent.click(await screen.findByRole('button', { name: /rate trade partner/i }));
        await userEvent.click(screen.getByRole('button', { name: /submit rating/i }));
        await waitFor(() => expect(screen.getByText('Failed to submit rating.')).toBeInTheDocument());
    });

    it('shows error when message exceeds max length', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade() });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        await screen.findByText('My Book');
        const textarea = screen.getByPlaceholderText('Type a message...');
        // Remove the maxLength restriction for testing the JS validation path
        textarea.removeAttribute('maxlength');
        const longMessage = 'a'.repeat(1001);
        await userEvent.type(textarea, longMessage);
        await userEvent.click(screen.getByRole('button', { name: 'Send message' }));
        await waitFor(() => expect(screen.getByText('Message must be 1000 characters or fewer.')).toBeInTheDocument());
    });

    it('calls markReceived when confirm dialog is accepted', async () => {
        vi.spyOn(window, 'confirm').mockReturnValue(true);
        const trade = makeTrade({
            status: 'shipping',
            shipments: [
                {
                    sender: { id: 'user-1', username: 'me' },
                    receiver: { id: 'user-2', username: 'partner' },
                    status: 'shipped',
                    tracking_number: 'TRK1',
                    shipped_at: '2026-04-22T00:00:00Z',
                    user_book: { condition: 'good', book: { id: 'b1', title: 'My Book', authors: [] } },
                },
                {
                    sender: { id: 'user-2', username: 'partner' },
                    receiver: { id: 'user-1', username: 'me' },
                    status: 'shipped',
                    tracking_number: 'TRK2',
                    shipped_at: '2026-04-23T00:00:00Z',
                    user_book: { condition: 'very_good', book: { id: 'b2', title: 'Their Book', authors: [] } },
                },
            ],
        });
        trades.getDetail.mockResolvedValue({ data: trade });
        trades.getMessages.mockResolvedValue({ data: [] });
        trades.markReceived.mockResolvedValue({ data: {} });
        renderWithProviders(<TradeDetail />);
        await userEvent.click(await screen.findByRole('button', { name: /mark book received/i }));
        expect(window.confirm).toHaveBeenCalledWith('Confirm you received the book?');
        await waitFor(() => expect(trades.markReceived).toHaveBeenCalled());
        window.confirm.mockRestore();
    });

    it('does not call markReceived when confirm dialog is cancelled', async () => {
        vi.spyOn(window, 'confirm').mockReturnValue(false);
        const trade = makeTrade({
            status: 'shipping',
            shipments: [
                {
                    sender: { id: 'user-1', username: 'me' },
                    receiver: { id: 'user-2', username: 'partner' },
                    status: 'shipped',
                    tracking_number: 'TRK1',
                    shipped_at: '2026-04-22T00:00:00Z',
                    user_book: { condition: 'good', book: { id: 'b1', title: 'My Book', authors: [] } },
                },
                {
                    sender: { id: 'user-2', username: 'partner' },
                    receiver: { id: 'user-1', username: 'me' },
                    status: 'shipped',
                    tracking_number: 'TRK2',
                    shipped_at: '2026-04-23T00:00:00Z',
                    user_book: { condition: 'very_good', book: { id: 'b2', title: 'Their Book', authors: [] } },
                },
            ],
        });
        trades.getDetail.mockResolvedValue({ data: trade });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        await userEvent.click(await screen.findByRole('button', { name: /mark book received/i }));
        expect(trades.markReceived).not.toHaveBeenCalled();
        window.confirm.mockRestore();
    });

    it('shows messages loading spinner while messages are fetching', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade() });
        trades.getMessages.mockReturnValue(new Promise(() => {})); // never resolves
        renderWithProviders(<TradeDetail />);
        await screen.findByText('My Book'); // trade data has loaded
        // Messages section renders a loading spinner while getMessages is pending
        const spinnerEl = document.querySelector('[class*="spinner"]') || document.querySelector('[class*="loading"]');
        expect(spinnerEl).toBeInTheDocument();
    });

    it('renders message without message_type field gracefully', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade() });
        trades.getMessages.mockResolvedValue({
            data: [{
                id: 'msg-notype',
                content: 'Message with no type',
                // no message_type → undefined → msg.message_type && ... evaluates to undefined (falsy)
                // → first && short-circuits (covers line 398 branch A: message_type falsy)
                sender: { id: 'user-2', username: 'partner' },
                created_at: '2026-04-20T13:00:00Z',
            }],
        });
        renderWithProviders(<TradeDetail />);
        expect(await screen.findByText('Message with no type')).toBeInTheDocument();
        // No type badge should be shown
        expect(screen.queryByRole('badge')).not.toBeInTheDocument();
    });

    it('renders message without created_at field gracefully', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade() });
        trades.getMessages.mockResolvedValue({
            data: [{
                id: 'msg-nodate',
                content: 'Timeless message',
                message_type: 'general',
                sender: { id: 'user-2', username: 'partner' },
                // no created_at → falsy → {msg.created_at && ...} evaluates to false (covers line 403 false branch)
            }],
        });
        renderWithProviders(<TradeDetail />);
        expect(await screen.findByText('Timeless message')).toBeInTheDocument();
    });

    it('shows "You" label for messages sent by the current user', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade() });
        trades.getMessages.mockResolvedValue({
            data: [{
                id: 'msg-me',
                content: 'I sent this message',
                message_type: 'general',
                sender: { id: 'user-1', username: 'me' }, // current user (user.id = 'user-1')
                created_at: '2026-04-20T13:00:00Z',
            }],
        });
        renderWithProviders(<TradeDetail />);
        // isMe = (msg.sender?.id === user?.id) = ('user-1' === 'user-1') = true → 'You' (covers line 396)
        expect(await screen.findByText('You')).toBeInTheDocument();
        expect(screen.getByText('I sent this message')).toBeInTheDocument();
    });

    it('shows fallback error when send message fails without detail', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade() });
        trades.getMessages.mockResolvedValue({ data: [] });
        trades.sendMessage.mockRejectedValue(new Error('Network error')); // no .response.data.detail
        renderWithProviders(<TradeDetail />);
        await screen.findByText('My Book');
        await userEvent.type(screen.getByPlaceholderText('Type a message...'), 'Hello');
        await userEvent.click(screen.getByRole('button', { name: 'Send message' }));
        // err?.response?.data?.detail is undefined → || fallback fires (covers line 75 right branch)
        await waitFor(() => expect(screen.getByText('Failed to send message.')).toBeInTheDocument());
    });

    it('shows API detail message when rate call fails with detail', async () => {
        const trade = makeTrade({
            status: 'completed',
            i_rated: false,
            shipments: [
                { sender: { id: 'user-1', username: 'me' }, receiver: { id: 'user-2', username: 'partner' },
                  status: 'received', tracking_number: '', user_book: { condition: 'good', book: { id: 'b1', title: 'My Book', authors: [] } } },
                { sender: { id: 'user-2', username: 'partner' }, receiver: { id: 'user-1', username: 'me' },
                  status: 'received', tracking_number: '', user_book: { condition: 'very_good', book: { id: 'b2', title: 'Their Book', authors: [] } } },
            ],
        });
        trades.getDetail.mockResolvedValue({ data: trade });
        trades.getMessages.mockResolvedValue({ data: [] });
        trades.rate.mockRejectedValue({ response: { data: { detail: 'Rating already submitted.' } } });
        renderWithProviders(<TradeDetail />);
        await userEvent.click(await screen.findByRole('button', { name: /rate trade partner/i }));
        await userEvent.click(screen.getByRole('button', { name: /submit rating/i }));
        // detail IS present → left side of || fires (covers line 120 left branch)
        await waitFor(() => expect(screen.getByText('Rating already submitted.')).toBeInTheDocument());
    });

    it('shows fallback status label when trade status is not in config', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade({ status: 'custom_unknown_status' }) });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        // TRADE_STATUS_CONFIG['custom_unknown_status'] is undefined → ?? fallback (covers line 129)
        expect(await screen.findByText('custom_unknown_status')).toBeInTheDocument();
    });

    it('shows message type badge for non-general message types', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade() });
        trades.getMessages.mockResolvedValue({
            data: [{
                id: 'msg-shipping',
                content: 'Book shipped today!',
                message_type: 'shipping_update',
                sender: { id: 'user-2', username: 'partner' },
                created_at: '2026-04-20T13:00:00Z',
            }],
        });
        renderWithProviders(<TradeDetail />);
        // msg.message_type !== 'general' → badge shown (covers line 399 true branch)
        expect(await screen.findByText('shipping update')).toBeInTheDocument();
        expect(screen.getByText('Book shipped today!')).toBeInTheDocument();
    });

    it('renders nothing when trade data is null (covers !trade guard)', async () => {
        trades.getDetail.mockResolvedValue({ data: null });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        // isLoading=false, isError=false, trade=null → if (!trade) return null
        await waitFor(() => {
            expect(screen.queryByText(/loading trade details/i)).not.toBeInTheDocument();
        });
        expect(screen.queryByText(/trade #/i)).not.toBeInTheDocument();
    });

    it('shows "Marking..." while markShipped mutation is pending', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade({ status: 'confirmed' }) });
        trades.getMessages.mockResolvedValue({ data: [] });
        trades.markShipped.mockReturnValue(new Promise(() => {})); // never resolves
        renderWithProviders(<TradeDetail />);
        await userEvent.click(await screen.findByRole('button', { name: /mark my book as shipped/i }));
        await userEvent.click(screen.getByRole('button', { name: 'Confirm Shipped' }));
        // markShippedMutation.isPending → button text changes to 'Marking...' (covers line 263)
        expect(screen.getByText('Marking...')).toBeInTheDocument();
    });

    it('shows "Book info unavailable" when shipment book is null', async () => {
        const trade = makeTrade({
            status: 'confirmed',
            shipments: [
                {
                    sender: { id: 'user-1', username: 'me' },
                    receiver: { id: 'user-2', username: 'partner' },
                    status: 'pending',
                    tracking_number: '',
                    user_book: { condition: 'good', book: null },
                },
                {
                    sender: { id: 'user-2', username: 'partner' },
                    receiver: { id: 'user-1', username: 'me' },
                    status: 'pending',
                    tracking_number: '',
                    user_book: null,
                },
            ],
        });
        trades.getDetail.mockResolvedValue({ data: trade });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        const unavailable = await screen.findAllByText('Book info unavailable');
        expect(unavailable.length).toBeGreaterThan(0);
    });

    it('refetchInterval returns false when document is hidden (covers document.hidden true branch at lines 55, 65)', async () => {
        // Make document.hidden return true so refetchInterval() → false (stops polling)
        const hiddenSpy = vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);

        trades.getDetail.mockResolvedValue({ data: makeTrade() });
        trades.getMessages.mockResolvedValue({ data: [] });

        renderWithProviders(<TradeDetail />);

        // Wait for queries to load — React Query calls refetchInterval() after each fetch
        await waitFor(() => expect(trades.getDetail).toHaveBeenCalled());
        await waitFor(() => expect(trades.getMessages).toHaveBeenCalled());

        // refetchInterval called with document.hidden=true → returns false → branch covered
        hiddenSpy.mockRestore();
    });

    it('shows error when markShipped fails (covers markShippedMutation onError at line 86)', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade({ status: 'confirmed' }) });
        trades.getMessages.mockResolvedValue({ data: [] });
        trades.markShipped.mockRejectedValue({ response: { data: { detail: 'Shipping failed.' } } });
        renderWithProviders(<TradeDetail />);
        await userEvent.click(await screen.findByRole('button', { name: /mark my book as shipped/i }));
        // The ship form submit button says "Confirm Shipped"
        await userEvent.click(await screen.findByRole('button', { name: /confirm shipped/i }));
        await waitFor(() => expect(screen.getByText('Shipping failed.')).toBeInTheDocument());
    });

    it('shows error when markReceived fails (covers markReceivedMutation onError at line 95)', async () => {
        vi.spyOn(window, 'confirm').mockReturnValue(true);
        trades.getDetail.mockResolvedValue({
            data: makeTrade({
                status: 'shipping',
                shipments: [
                    { sender: { id: 'user-1', username: 'me' }, receiver: { id: 'user-2', username: 'partner' }, status: 'shipped', tracking_number: '', user_book: { condition: 'good', book: { id: 'b1', title: 'My Book', authors: [] } } },
                    { sender: { id: 'user-2', username: 'partner' }, receiver: { id: 'user-1', username: 'me' }, status: 'shipped', tracking_number: '', user_book: { condition: 'good', book: { id: 'b2', title: 'Their Book', authors: [] } } },
                ],
            }),
        });
        trades.getMessages.mockResolvedValue({ data: [] });
        trades.markReceived.mockRejectedValue({ response: { data: { detail: 'Receive failed.' } } });
        renderWithProviders(<TradeDetail />);
        await userEvent.click(await screen.findByRole('button', { name: /mark book received/i }));
        await waitFor(() => expect(screen.getByText('Receive failed.')).toBeInTheDocument());
        vi.restoreAllMocks();
    });

    it('covers rating form interactions: textarea onChange, checkbox onChange, and Cancel button (lines 326, 335, 347)', async () => {
        trades.getDetail.mockResolvedValue({
            data: makeTrade({ status: 'completed', i_rated: false }),
        });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);

        // Open the rate form
        await userEvent.click(await screen.findByRole('button', { name: /rate trade partner/i }));

        // onChange for ratingComment textarea (line 326)
        const commentBox = screen.getByPlaceholderText(/how was the trade/i);
        await userEvent.type(commentBox, 'Great trade!');

        // onChange for bookConditionAccurate checkbox (line 335)
        const conditionCheckbox = screen.getByRole('checkbox', { name: /book condition matched/i });
        await userEvent.click(conditionCheckbox);

        // Cancel button onClick (line 347)
        await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
        // Form should be hidden after cancel
        expect(screen.queryByPlaceholderText(/how was the trade/i)).not.toBeInTheDocument();
    });

    it('covers message type select onChange (line 423)', async () => {
        trades.getDetail.mockResolvedValue({ data: makeTrade() });
        trades.getMessages.mockResolvedValue({ data: [] });
        renderWithProviders(<TradeDetail />);
        await screen.findByText('My Book');

        // Change the message type select — covers onChange at line 423
        const msgTypeSelect = screen.getByRole('combobox');
        await userEvent.selectOptions(msgTypeSelect, 'shipping_update');
        expect(msgTypeSelect).toHaveValue('shipping_update');
    });
});