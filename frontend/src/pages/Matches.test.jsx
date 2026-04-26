import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Matches from './Matches.jsx';

vi.mock('../services/api.js', () => ({
    matches: {
        list: vi.fn(),
        accept: vi.fn(),
        decline: vi.fn(),
    },
}));

vi.mock('../hooks/useAuth.js', () => ({
    default: vi.fn(() => ({ user: { id: 'user-1', username: 'bart0605' } })),
}));

import { matches } from '../services/api.js';

describe('Matches page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders match books from the current API shape and accepts a match', async () => {
        matches.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'match-1',
                        status: 'pending',
                        match_type: 'direct',
                        legs: [
                            {
                                sender: { id: 'user-1', username: 'bart0605' },
                                receiver: { id: 'user-2', username: 'alice', avg_recent_rating: 4.7 },
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
                                sender: { id: 'user-2', username: 'alice', avg_recent_rating: 4.7 },
                                receiver: { id: 'user-1', username: 'bart0605' },
                                user_book: {
                                    condition: 'very_good',
                                    book: {
                                        id: 'book-2',
                                        title: 'The Dispossessed',
                                        authors: ['Ursula K. Le Guin'],
                                        cover_image_url: 'https://example.com/dispossessed.jpg',
                                    },
                                },
                            },
                        ],
                    },
                ],
            },
        });
        matches.accept.mockResolvedValue({ data: {} });

        renderWithProviders(<Matches />);

        expect(await screen.findByText('Kindred')).toBeInTheDocument();
        expect(screen.getByText('Octavia E. Butler')).toBeInTheDocument();
        expect(screen.getByText('The Dispossessed')).toBeInTheDocument();
        expect(screen.getByText('Ursula K. Le Guin')).toBeInTheDocument();
        expect(screen.getByAltText('Kindred')).toHaveAttribute('src', 'https://example.com/kindred.jpg');
        expect(screen.getByAltText('The Dispossessed')).toHaveAttribute('src', 'https://example.com/dispossessed.jpg');

        await userEvent.click(screen.getByRole('button', { name: 'Accept Match' }));

        await waitFor(() => {
            expect(matches.accept).toHaveBeenCalledWith('match-1');
        });
    });

    it('shows verify address CTA when accept fails with address verification required', async () => {
        matches.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'match-1',
                        status: 'pending',
                        match_type: 'direct',
                        legs: [
                            {
                                sender: { id: 'user-1', username: 'bart0605' },
                                receiver: { id: 'user-2', username: 'alice' },
                                user_book: { condition: 'good', book: { id: 'book-1', title: 'Kindred', authors: ['Octavia E. Butler'] } },
                            },
                            {
                                sender: { id: 'user-2', username: 'alice' },
                                receiver: { id: 'user-1', username: 'bart0605' },
                                user_book: { condition: 'very_good', book: { id: 'book-2', title: 'The Dispossessed', authors: ['Ursula K. Le Guin'] } },
                            },
                        ],
                    },
                ],
            },
        });
        matches.accept.mockRejectedValue({
            response: {
                data: {
                    detail: 'You need a USPS-verified shipping address before accepting a match.',
                    code: 'address_verification_required',
                    verification_url: '/account',
                },
            },
        });

        renderWithProviders(<Matches />);
        await userEvent.click(await screen.findByRole('button', { name: 'Accept Match' }));

        expect(await screen.findByText(/USPS-verified shipping address/i)).toBeInTheDocument();
        expect(screen.getByRole('link', { name: /verify address now/i })).toHaveAttribute('href', '/account');
    });

    it('shows loading spinner while fetching', () => {
        matches.list.mockReturnValue(new Promise(() => {}));
        renderWithProviders(<Matches />);
        expect(document.querySelector('[class*="spinner"]') || document.querySelector('[class*="loading"]')).toBeTruthy();
    });

    it('shows error message when match fetch fails', async () => {
        matches.list.mockRejectedValue(new Error('Network error'));
        renderWithProviders(<Matches />);
        expect(await screen.findByText(/network error/i)).toBeInTheDocument();
    });

    it('shows empty state when no matches found (all tab)', async () => {
        matches.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Matches />);
        // Default tab is 'pending', switch to 'all' to see "no matches found"
        const allTab = await screen.findByRole('button', { name: /^all$/i });
        await userEvent.click(allTab);
        expect(await screen.findByText(/no matches found/i)).toBeInTheDocument();
    });

    it('shows "No pending matches" when pending tab active and empty', async () => {
        matches.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Matches />);
        const pendingTab = await screen.findByRole('button', { name: /^pending$/i });
        await userEvent.click(pendingTab);
        expect(await screen.findByText(/no pending matches/i)).toBeInTheDocument();
    });

    it('shows "Book info unavailable" for match leg with no book data', async () => {
        matches.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'match-2',
                        status: 'pending',
                        match_type: 'direct',
                        legs: [
                            {
                                sender: { id: 'user-1', username: 'bart0605' },
                                receiver: { id: 'user-2', username: 'alice' },
                                user_book: null,
                            },
                            {
                                sender: { id: 'user-2', username: 'alice' },
                                receiver: { id: 'user-1', username: 'bart0605' },
                                user_book: null,
                            },
                        ],
                    },
                ],
            },
        });
        renderWithProviders(<Matches />);
        const unavailable = await screen.findAllByText(/book info unavailable/i);
        expect(unavailable.length).toBeGreaterThan(0);
    });

    it('shows fallback "Failed to accept match." when accept fails without detail field (covers || right side line 58)', async () => {
        matches.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'match-9',
                        status: 'pending',
                        match_type: 'direct',
                        legs: [
                            { sender: { id: 'user-1', username: 'bart0605' }, receiver: { id: 'user-2', username: 'alice' }, user_book: { condition: 'good', book: { id: 'b13', title: 'Book G', authors: ['Author'] } } },
                            { sender: { id: 'user-2', username: 'alice' }, receiver: { id: 'user-1', username: 'bart0605' }, user_book: { condition: 'good', book: { id: 'b14', title: 'Book H', authors: ['Author2'] } } },
                        ],
                    },
                ],
            },
        });
        // No detail field → falls back to 'Failed to accept match.'
        matches.accept.mockRejectedValue({ response: { data: {} } });
        renderWithProviders(<Matches />);
        await userEvent.click(await screen.findByRole('button', { name: 'Accept Match' }));
        await waitFor(() => expect(screen.getByText('Failed to accept match.')).toBeInTheDocument());
    });

    it('uses /account fallback when accept fails with address code but no verification_url (covers || right side line 61)', async () => {
        matches.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'match-10',
                        status: 'pending',
                        match_type: 'direct',
                        legs: [
                            { sender: { id: 'user-1', username: 'bart0605' }, receiver: { id: 'user-2', username: 'alice' }, user_book: { condition: 'good', book: { id: 'b15', title: 'Book I', authors: ['Author'] } } },
                            { sender: { id: 'user-2', username: 'alice' }, receiver: { id: 'user-1', username: 'bart0605' }, user_book: { condition: 'good', book: { id: 'b16', title: 'Book J', authors: ['Author2'] } } },
                        ],
                    },
                ],
            },
        });
        // code is set but NO verification_url → falls back to '/account'
        matches.accept.mockRejectedValue({
            response: {
                data: {
                    detail: 'Address required.',
                    code: 'address_verification_required',
                    // no verification_url
                },
            },
        });
        renderWithProviders(<Matches />);
        await userEvent.click(await screen.findByRole('button', { name: 'Accept Match' }));
        const link = await screen.findByRole('link', { name: /verify address now/i });
        expect(link).toHaveAttribute('href', '/account');
    });

    it('shows generic error when accept fails without address code', async () => {
        matches.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'match-4',
                        status: 'pending',
                        match_type: 'direct',
                        legs: [
                            { sender: { id: 'user-1', username: 'bart0605' }, receiver: { id: 'user-2', username: 'alice' }, user_book: { condition: 'good', book: { id: 'b1', title: 'Book A', authors: ['Author'] } } },
                            { sender: { id: 'user-2', username: 'alice' }, receiver: { id: 'user-1', username: 'bart0605' }, user_book: { condition: 'good', book: { id: 'b2', title: 'Book B', authors: ['Author2'] } } },
                        ],
                    },
                ],
            },
        });
        matches.accept.mockRejectedValue({ response: { data: { detail: 'Server error.' } } });
        renderWithProviders(<Matches />);
        await userEvent.click(await screen.findByRole('button', { name: /accept match/i }));
        await waitFor(() => expect(screen.getByText('Server error.')).toBeInTheDocument());
    });

    it('shows generic decline error when decline fails', async () => {
        matches.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'match-5',
                        status: 'pending',
                        match_type: 'direct',
                        legs: [
                            { sender: { id: 'user-1', username: 'bart0605' }, receiver: { id: 'user-2', username: 'alice' }, user_book: { condition: 'good', book: { id: 'b3', title: 'Book C', authors: ['Author'] } } },
                            { sender: { id: 'user-2', username: 'alice' }, receiver: { id: 'user-1', username: 'bart0605' }, user_book: { condition: 'good', book: { id: 'b4', title: 'Book D', authors: ['Author2'] } } },
                        ],
                    },
                ],
            },
        });
        matches.decline.mockRejectedValue(new Error('Network failure'));
        renderWithProviders(<Matches />);
        await userEvent.click(await screen.findByRole('button', { name: /^decline$/i }));
        await waitFor(() => expect(screen.getByText(/failed to decline match/i)).toBeInTheDocument());
    });

    it('shows specific detail error when decline fails with detail field', async () => {
        matches.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'match-6',
                        status: 'pending',
                        match_type: 'direct',
                        legs: [
                            { sender: { id: 'user-1', username: 'bart0605' }, receiver: { id: 'user-2', username: 'alice' }, user_book: { condition: 'good', book: { id: 'b5', title: 'Book E', authors: ['Author'] } } },
                            { sender: { id: 'user-2', username: 'alice' }, receiver: { id: 'user-1', username: 'bart0605' }, user_book: { condition: 'good', book: { id: 'b6', title: 'Book F', authors: ['Author2'] } } },
                        ],
                    },
                ],
            },
        });
        matches.decline.mockRejectedValue({
            response: { data: { detail: 'You cannot decline this match right now.' } },
        });
        renderWithProviders(<Matches />);
        await userEvent.click(await screen.findByRole('button', { name: /^decline$/i }));
        await waitFor(() =>
            expect(screen.getByText('You cannot decline this match right now.')).toBeInTheDocument()
        );
    });

    it('renders matches from array-format API response (covers Array.isArray(data) true branch)', async () => {
        matches.list.mockResolvedValue({
            data: [
                {
                    id: 'match-arr-1',
                    status: 'accepted',
                    match_type: 'direct',
                    legs: [
                        { sender: { id: 'user-1', username: 'bart0605' }, receiver: { id: 'user-2', username: 'alice' }, user_book: { condition: 'good', book: { id: 'b7', title: 'Array Book A', authors: ['Array Author'] } } },
                        { sender: { id: 'user-2', username: 'alice' }, receiver: { id: 'user-1', username: 'bart0605' }, user_book: { condition: 'good', book: { id: 'b8', title: 'Array Book B', authors: ['Array Author 2'] } } },
                    ],
                },
            ],
        });
        renderWithProviders(<Matches />);
        expect(await screen.findByText('Array Book A')).toBeInTheDocument();
        expect(screen.getByText('Array Book B')).toBeInTheDocument();
    });

    it('shows raw status label for unknown match status (covers STATUS_CONFIG ?? fallback)', async () => {
        matches.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'match-7',
                        status: 'ring_expired',
                        match_type: 'ring',
                        legs: [
                            { sender: { id: 'user-1', username: 'bart0605' }, receiver: { id: 'user-2', username: 'alice' }, user_book: { condition: 'good', book: { id: 'b9', title: 'Ring Book A', authors: ['Author'] } } },
                            { sender: { id: 'user-2', username: 'alice' }, receiver: { id: 'user-1', username: 'bart0605' }, user_book: { condition: 'good', book: { id: 'b10', title: 'Ring Book B', authors: ['Author2'] } } },
                        ],
                    },
                ],
            },
        });
        renderWithProviders(<Matches />);
        expect(await screen.findByText('ring_expired')).toBeInTheDocument();
    });

    it('clears action error after successful decline (covers declineMutation onSuccess)', async () => {
        matches.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'match-8',
                        status: 'pending',
                        match_type: 'direct',
                        legs: [
                            { sender: { id: 'user-1', username: 'bart0605' }, receiver: { id: 'user-2', username: 'alice' }, user_book: { condition: 'good', book: { id: 'b11', title: 'Clear Error Book A', authors: ['Author'] } } },
                            { sender: { id: 'user-2', username: 'alice' }, receiver: { id: 'user-1', username: 'bart0605' }, user_book: { condition: 'good', book: { id: 'b12', title: 'Clear Error Book B', authors: ['Author2'] } } },
                        ],
                    },
                ],
            },
        });
        // First: accept fails to set an error
        matches.accept.mockRejectedValueOnce({ response: { data: { detail: 'Accept failed error.' } } });
        // Then: decline succeeds to clear the error
        matches.decline.mockResolvedValue({ data: {} });

        renderWithProviders(<Matches />);
        await screen.findByText('Clear Error Book A');

        // Trigger accept to set an error
        await userEvent.click(screen.getByRole('button', { name: 'Accept Match' }));
        await waitFor(() => expect(screen.getByText('Accept failed error.')).toBeInTheDocument());

        // Decline success should clear the error via onSuccess → setActionError(null)
        await userEvent.click(screen.getByRole('button', { name: /^decline$/i }));
        await waitFor(() => expect(screen.queryByText('Accept failed error.')).not.toBeInTheDocument());
    });

    it('declines a match', async () => {
        matches.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'match-3',
                        status: 'pending',
                        match_type: 'direct',
                        legs: [
                            {
                                sender: { id: 'user-1', username: 'bart0605' },
                                receiver: { id: 'user-2', username: 'alice' },
                                user_book: { condition: 'good', book: { id: 'book-1', title: 'Test Book', authors: ['Author'] } },
                            },
                            {
                                sender: { id: 'user-2', username: 'alice' },
                                receiver: { id: 'user-1', username: 'bart0605' },
                                user_book: { condition: 'good', book: { id: 'book-2', title: 'Another Book', authors: ['Author2'] } },
                            },
                        ],
                    },
                ],
            },
        });
        matches.decline.mockResolvedValue({ data: {} });
        renderWithProviders(<Matches />);
        await userEvent.click(await screen.findByRole('button', { name: /^decline$/i }));
        await waitFor(() => expect(matches.decline).toHaveBeenCalledWith('match-3'));
    });
});