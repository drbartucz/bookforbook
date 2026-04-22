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
        counter: vi.fn(),
    },
}));

import { proposals } from '../services/api.js';

describe('Proposals page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
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
                        receiver: { id: 'user-1', username: 'bart0605' },
                        note: 'Interested in trading?',
                        offered_book: {
                            condition: 'good',
                            book: {
                                id: 'book-1',
                                title: 'The Dispossessed',
                                authors: ['Ursula K. Le Guin'],
                                cover_image_url: 'https://example.com/dispossessed.jpg',
                            },
                        },
                        requested_book: {
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
});