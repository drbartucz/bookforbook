import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Donations from './Donations.jsx';

vi.mock('../services/api.js', () => ({
    donations: {
        list: vi.fn(),
        accept: vi.fn(),
        decline: vi.fn(),
    },
}));

import { donations } from '../services/api.js';

describe('Donations page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders donation books from the current API shape and accepts a donation', async () => {
        donations.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'donation-1',
                        status: 'offered',
                        created_at: '2026-04-20T12:00:00Z',
                        is_recipient: true,
                        donor: { id: 'user-1', username: 'bart0605' },
                        institution: { id: 'inst-1', username: 'central-library' },
                        user_book: {
                            condition: 'good',
                            book: {
                                id: 'book-1',
                                title: 'The Bluest Eye',
                                authors: ['Toni Morrison'],
                                cover_image_url: 'https://example.com/bluesteye.jpg',
                            },
                        },
                    },
                ],
            },
        });
        donations.accept.mockResolvedValue({ data: {} });

        renderWithProviders(<Donations />);

        expect(await screen.findByText('The Bluest Eye')).toBeInTheDocument();
        expect(screen.getByText('Toni Morrison')).toBeInTheDocument();
        expect(screen.getByAltText('The Bluest Eye')).toHaveAttribute('src', 'https://example.com/bluesteye.jpg');
        expect(screen.getByText('@central-library')).toBeInTheDocument();

        await userEvent.click(screen.getByRole('button', { name: 'Accept Donation' }));

        await waitFor(() => {
            expect(donations.accept).toHaveBeenCalledWith('donation-1');
        });
    });

    it('shows loading spinner while fetching', () => {
        donations.list.mockReturnValue(new Promise(() => {}));
        renderWithProviders(<Donations />);
        expect(document.querySelector('[class*="spinner"]') || document.querySelector('[class*="loading"]')).toBeTruthy();
    });

    it('shows error message when donation fetch fails', async () => {
        donations.list.mockRejectedValue(new Error('Network error'));
        renderWithProviders(<Donations />);
        expect(await screen.findByText(/network error/i)).toBeInTheDocument();
    });

    it('shows empty state when no donations found', async () => {
        donations.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Donations />);
        expect(await screen.findByText(/no donations found/i)).toBeInTheDocument();
    });

    it('shows "Book info unavailable" when book data is missing', async () => {
        donations.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'donation-2',
                        status: 'offered',
                        created_at: '2026-04-20T12:00:00Z',
                        is_recipient: false,
                        donor: { id: 'user-1', username: 'alice' },
                        institution: { id: 'inst-1', username: 'library' },
                        user_book: null,
                        book: null,
                    },
                ],
            },
        });
        renderWithProviders(<Donations />);
        expect(await screen.findByText(/book info unavailable/i)).toBeInTheDocument();
    });

    it('shows action error when accept fails', async () => {
        donations.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'donation-4',
                        status: 'offered',
                        created_at: '2026-04-20T12:00:00Z',
                        is_recipient: true,
                        donor: { id: 'user-1', username: 'alice' },
                        institution: { id: 'inst-1', username: 'library' },
                        user_book: { condition: 'good', book: { id: 'book-5', title: 'Error Book', authors: ['Author'] } },
                    },
                ],
            },
        });
        donations.accept.mockRejectedValue({ response: { data: { detail: 'Cannot accept this donation.' } } });
        renderWithProviders(<Donations />);
        await userEvent.click(await screen.findByRole('button', { name: 'Accept Donation' }));
        await waitFor(() => expect(screen.getByText('Cannot accept this donation.')).toBeInTheDocument());
    });

    it('renders donation using fallback fields (from_user, recipient.name, unknown status)', async () => {
        donations.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'donation-fallback',
                        status: 'returned',  // not in STATUS_CONFIG → triggers ?? fallback at line 106
                        created_at: '2026-04-20T12:00:00Z',
                        // is_recipient absent → ?? false at line 112
                        from_user: { id: 'user-1', username: 'alice' },  // donor ?? from_user at line 109
                        recipient: { id: 'inst-1', name: 'City Library' },  // no username → name fallback at line 156
                        user_book: {
                            condition: 'good',
                            book: { id: 'book-fb', title: 'Fallback Book', authors: ['Author'] },
                        },
                    },
                ],
            },
        });
        renderWithProviders(<Donations />);
        expect(await screen.findByText('Fallback Book')).toBeInTheDocument();
        expect(screen.getByText('@alice')).toBeInTheDocument();
        expect(screen.getByText('@City Library')).toBeInTheDocument();
        // Unknown status should use the raw status text as label
        expect(screen.getByText('returned')).toBeInTheDocument();
    });

    it('filters by direction when a direction tab is clicked', async () => {
        donations.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Donations />);
        await screen.findByText(/no donations found/i);
        // Click the "Offered by me" tab to set direction state
        const offeredTab = screen.getByRole('button', { name: /offered by me/i });
        await userEvent.click(offeredTab);
        await waitFor(() => {
            expect(donations.list).toHaveBeenCalledWith(expect.objectContaining({ direction: 'offered' }));
        });
    });

    it('shows generic error when accept fails without detail', async () => {
        donations.list.mockResolvedValue({
            data: {
                count: 1,
                results: [{
                    id: 'donation-5',
                    status: 'offered',
                    created_at: '2026-04-20T12:00:00Z',
                    is_recipient: true,
                    donor: { id: 'user-1', username: 'alice' },
                    institution: { id: 'inst-1', username: 'library' },
                    user_book: { condition: 'good', book: { id: 'book-5', title: 'Error Book', authors: [] } },
                }],
            },
        });
        donations.accept.mockRejectedValueOnce({ response: { data: {} } });
        renderWithProviders(<Donations />);
        await userEvent.click(await screen.findByRole('button', { name: 'Accept Donation' }));
        await waitFor(() => expect(screen.getByText('Failed to accept.')).toBeInTheDocument());
    });

    it('renders when API returns array format directly', async () => {
        donations.list.mockResolvedValue({
            data: [
                {
                    id: 'donation-arr',
                    status: 'offered',
                    created_at: '2026-04-20T12:00:00Z',
                    is_recipient: false,
                    donor: { id: 'user-1', username: 'sender' },
                    institution: { id: 'inst-1', username: 'lib' },
                    user_book: { condition: 'good', book: { id: 'book-a', title: 'Array Book', authors: ['Writer'] } },
                },
            ],
        });
        renderWithProviders(<Donations />);
        expect(await screen.findByText('Array Book')).toBeInTheDocument();
    });

    it('renders donation using to_user fallback when institution and recipient are absent', async () => {
        donations.list.mockResolvedValue({
            data: {
                count: 1,
                results: [{
                    id: 'donation-tou',
                    status: 'offered',
                    created_at: '2026-04-20T12:00:00Z',
                    is_recipient: false,
                    donor: { id: 'user-1', username: 'alice' },
                    // No institution or recipient — falls back to to_user
                    to_user: { id: 'inst-2', username: 'community-lib' },
                    user_book: { condition: 'good', book: { id: 'book-tou', title: 'To User Book', authors: [] } },
                }],
            },
        });
        renderWithProviders(<Donations />);
        expect(await screen.findByText('To User Book')).toBeInTheDocument();
        expect(screen.getByText('@community-lib')).toBeInTheDocument();
    });

    it('declines a donation', async () => {
        donations.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'donation-3',
                        status: 'offered',
                        created_at: '2026-04-20T12:00:00Z',
                        is_recipient: true,
                        donor: { id: 'user-1', username: 'bart0605' },
                        institution: { id: 'inst-1', username: 'library' },
                        user_book: {
                            condition: 'good',
                            book: { id: 'book-3', title: 'Test Book', authors: ['Author'] },
                        },
                    },
                ],
            },
        });
        donations.decline.mockResolvedValue({ data: {} });
        renderWithProviders(<Donations />);
        await userEvent.click(await screen.findByRole('button', { name: /decline/i }));
        await waitFor(() => expect(donations.decline).toHaveBeenCalledWith('donation-3'));
    });

    it('shows action error when decline mutation fails (covers declineMutation onError at line 58)', async () => {
        donations.list.mockResolvedValue({
            data: {
                count: 1,
                results: [{
                    id: 'donation-err',
                    status: 'offered',
                    created_at: '2026-04-20T12:00:00Z',
                    is_recipient: true,
                    donor: { id: 'user-2', username: 'bob' },
                    institution: { id: 'inst-1', username: 'library' },
                    user_book: { condition: 'good', book: { id: 'bk1', title: 'Error Book', authors: [] } },
                }],
            },
        });
        donations.decline.mockRejectedValue({ response: { data: { detail: 'Cannot decline this donation.' } } });
        renderWithProviders(<Donations />);
        await userEvent.click(await screen.findByRole('button', { name: /decline/i }));
        await waitFor(() => expect(screen.getByText('Cannot decline this donation.')).toBeInTheDocument());
    });
});