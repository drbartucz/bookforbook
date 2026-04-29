import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Proposals from './Proposals.jsx';

vi.mock('../services/api.js', () => ({
    proposals: {
        list: vi.fn(),
        accept: vi.fn(),
        decline: vi.fn(),
    },
}));

vi.mock('../hooks/useAuth.js', () => ({
    default: vi.fn(),
}));

import { proposals } from '../services/api.js';
import useAuth from '../hooks/useAuth.js';

describe('Proposals page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        useAuth.mockReturnValue({ user: { id: 'user-1' } });
    });

    it('renders proposal books from the current API shape and accepts a proposal', async () => {
        proposals.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'proposal-1',
                        status: 'pending',
                        proposer: { id: 'user-2', username: 'alice' },
                        recipient: { id: 'user-1', username: 'bart0605' },
                        message: 'Interested in trading?',
                        items: [
                            {
                                direction: 'proposer_sends',
                                user_book: {
                                    id: 'ub-1',
                                    condition: 'good',
                                    book: {
                                        id: 'book-1',
                                        title: 'The Dispossessed',
                                        authors: ['Ursula K. Le Guin'],
                                        cover_image_url: 'https://example.com/dispossessed.jpg',
                                    },
                                },
                            },
                            {
                                direction: 'recipient_sends',
                                user_book: {
                                    id: 'ub-2',
                                    condition: 'very_good',
                                    book: {
                                        id: 'book-2',
                                        title: 'Kindred',
                                        authors: ['Octavia E. Butler'],
                                        cover_image_url: 'https://example.com/kindred.jpg',
                                    },
                                },
                            },
                        ],
                    },
                ],
            },
        });
        proposals.accept.mockResolvedValue({ data: {} });

        renderWithProviders(<Proposals />);

        expect(await screen.findByText('The Dispossessed')).toBeInTheDocument();
        expect(screen.getByText('Ursula K. Le Guin')).toBeInTheDocument();
        expect(screen.getByText('Kindred')).toBeInTheDocument();
        expect(screen.getByText('Octavia E. Butler')).toBeInTheDocument();
        expect(screen.getByAltText('The Dispossessed')).toHaveAttribute(
            'src',
            'https://example.com/dispossessed.jpg'
        );
        expect(screen.getByAltText('Kindred')).toHaveAttribute(
            'src',
            'https://example.com/kindred.jpg'
        );
        expect(screen.getByText(/Interested in trading\?/)).toBeInTheDocument();

        await userEvent.click(screen.getByRole('button', { name: 'Accept' }));

        await waitFor(() => {
            expect(proposals.accept).toHaveBeenCalledWith('proposal-1');
        });
    });

    it('shows action error when accept fails', async () => {
        proposals.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'proposal-err',
                        status: 'pending',
                        proposer: { id: 'user-2', username: 'alice' },
                        recipient: { id: 'user-1', username: 'bart0605' },
                        items: [
                            { direction: 'proposer_sends', user_book: { id: 'ub-a', condition: 'good', book: { id: 'ba', title: 'Dune 2', authors: ['Herbert'] } } },
                            { direction: 'recipient_sends', user_book: { id: 'ub-b', condition: 'good', book: { id: 'bb', title: 'Dune 3', authors: ['Herbert'] } } },
                        ],
                    },
                ],
            },
        });
        proposals.accept.mockRejectedValue({ response: { data: { detail: 'Proposal already closed.' } } });
        renderWithProviders(<Proposals />);
        await userEvent.click(await screen.findByRole('button', { name: 'Accept' }));
        await waitFor(() => expect(screen.getByText('Proposal already closed.')).toBeInTheDocument());
    });

    it('shows loading spinner while fetching', () => {
        proposals.list.mockReturnValue(new Promise(() => { }));
        renderWithProviders(<Proposals />);
        expect(document.querySelector('[class*="spinner"]') || document.querySelector('[class*="loading"]')).toBeTruthy();
    });

    it('shows error message when proposals fetch fails', async () => {
        proposals.list.mockRejectedValue(new Error('Network error'));
        renderWithProviders(<Proposals />);
        expect(await screen.findByText(/network error/i)).toBeInTheDocument();
    });

    it('shows empty state when no proposals found', async () => {
        proposals.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Proposals />);
        expect(await screen.findByText(/no proposals found/i)).toBeInTheDocument();
    });

    it('declines a proposal', async () => {
        proposals.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'proposal-2',
                        status: 'pending',
                        proposer: { id: 'user-2', username: 'alice' },
                        recipient: { id: 'user-1', username: 'bart0605' },
                        items: [
                            {
                                direction: 'proposer_sends',
                                user_book: { id: 'ub-1', condition: 'good', book: { id: 'book-1', title: 'Dune', authors: ['Frank Herbert'] } },
                            },
                            {
                                direction: 'recipient_sends',
                                user_book: { id: 'ub-2', condition: 'good', book: { id: 'book-2', title: 'Foundation', authors: ['Isaac Asimov'] } },
                            },
                        ],
                    },
                ],
            },
        });
        proposals.decline.mockResolvedValue({ data: {} });
        renderWithProviders(<Proposals />);
        await userEvent.click(await screen.findByRole('button', { name: 'Decline' }));
        await waitFor(() => expect(proposals.decline).toHaveBeenCalledWith('proposal-2'));
    });

    it('renders proposals from paginated API response', async () => {
        proposals.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'proposal-arr',
                        status: 'accepted',
                        proposer: { id: 'user-2', username: 'alice' },
                        recipient: { id: 'user-1', username: 'bart0605' },
                        items: [
                            { direction: 'proposer_sends', user_book: { id: 'ub-1', condition: 'good', book: { id: 'b1', title: 'Array Book A', authors: [] } } },
                            { direction: 'recipient_sends', user_book: { id: 'ub-2', condition: 'good', book: { id: 'b2', title: 'Array Book B', authors: [] } } },
                        ],
                    },
                ],
            },
        });
        renderWithProviders(<Proposals />);
        expect(await screen.findByText('Array Book A')).toBeInTheDocument();
        expect(screen.getAllByText('Accepted').length).toBeGreaterThan(0);
    });

    it('shows generic fallback error when accept fails without detail', async () => {
        proposals.list.mockResolvedValue({
            data: {
                count: 1,
                results: [{
                    id: 'proposal-err2',
                    status: 'pending',
                    proposer: { id: 'user-2', username: 'alice' },
                    recipient: { id: 'user-1', username: 'bart0605' },
                    items: [
                        { direction: 'proposer_sends', user_book: { id: 'ub-1', condition: 'good', book: { id: 'b1', title: 'Book X', authors: [] } } },
                        { direction: 'recipient_sends', user_book: { id: 'ub-2', condition: 'good', book: { id: 'b2', title: 'Book Y', authors: [] } } },
                    ],
                }],
            },
        });
        proposals.accept.mockRejectedValueOnce({ response: { data: {} } });
        renderWithProviders(<Proposals />);
        await userEvent.click(await screen.findByRole('button', { name: 'Accept' }));
        await waitFor(() => expect(screen.getByText('Failed to accept.')).toBeInTheDocument());
    });

    it('hides action buttons for proposals when direction is "sent"', async () => {
        proposals.list.mockResolvedValue({
            data: {
                count: 1,
                results: [{
                    id: 'proposal-sent',
                    status: 'pending',
                    proposer: { id: 'user-1', username: 'bart0605' },
                    recipient: { id: 'user-2', username: 'alice' },
                    items: [
                        { direction: 'proposer_sends', user_book: { id: 'ub-1', condition: 'good', book: { id: 'b1', title: 'My Sent Book', authors: ['A'] } } },
                        { direction: 'recipient_sends', user_book: { id: 'ub-2', condition: 'good', book: { id: 'b2', title: 'Their Book', authors: ['B'] } } },
                    ],
                }],
            },
        });
        renderWithProviders(<Proposals />);
        await screen.findByText('My Sent Book');
        // Click the "Sent" direction tab — direction becomes 'sent', canAct = false → no action buttons
        await userEvent.click(screen.getByRole('button', { name: 'Sent' }));
        await waitFor(() => {
            expect(proposals.list).toHaveBeenCalledWith(expect.objectContaining({ direction: 'sent' }));
        });
        expect(screen.queryByRole('button', { name: 'Accept' })).not.toBeInTheDocument();
    });

    it('renders proposal using sender/receiver field names (fallback from proposer/recipient)', async () => {
        proposals.list.mockResolvedValue({
            data: {
                count: 1,
                results: [{
                    id: 'proposal-fallback',
                    status: 'unknown_custom_status',
                    sender: { id: 'user-2', username: 'alice' },
                    receiver: { id: 'user-1', username: 'bart0605' },
                    items: [
                        { direction: 'proposer_sends', user_book: { id: 'ub-1', condition: 'good', book: { id: 'b1', title: 'Fallback Book A', authors: ['Author A'] } } },
                        { direction: 'recipient_sends', user_book: { id: 'ub-2', condition: 'good', book: { id: 'b2', title: 'Fallback Book B', authors: ['Author B'] } } },
                    ],
                }],
            },
        });
        renderWithProviders(<Proposals />);
        expect(await screen.findByText('Fallback Book A')).toBeInTheDocument();
        expect(screen.getByText('@alice')).toBeInTheDocument();
        expect(screen.getByText('unknown_custom_status')).toBeInTheDocument();
    });

    it('shows action error when decline mutation fails', async () => {
        proposals.list.mockResolvedValue({
            data: {
                count: 1,
                results: [{
                    id: 'proposal-err',
                    status: 'pending',
                    proposer: { id: 'user-2', username: 'alice' },
                    recipient: { id: 'user-1', username: 'bart0605' },
                    items: [
                        { direction: 'proposer_sends', user_book: { id: 'ub-1', condition: 'good', book: { id: 'bk1', title: 'Decline Error Book', authors: [] } } },
                        { direction: 'recipient_sends', user_book: { id: 'ub-2', condition: 'good', book: { id: 'bk2', title: 'Their Book', authors: [] } } },
                    ],
                }],
            },
        });
        proposals.decline.mockRejectedValue({ response: { data: { detail: 'Cannot decline.' } } });
        renderWithProviders(<Proposals />);
        await userEvent.click(await screen.findByRole('button', { name: 'Decline' }));
        await waitFor(() => expect(screen.getByText('Cannot decline.')).toBeInTheDocument());
    });

    it('filters proposals by status tab click', async () => {
        proposals.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Proposals />);
        await screen.findByText('No proposals found');
        await userEvent.click(screen.getByRole('button', { name: 'Accepted' }));
        await waitFor(() => expect(proposals.list).toHaveBeenCalledWith(expect.objectContaining({ status: 'accepted' })));
    });
});
