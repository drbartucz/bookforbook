import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Discovery from './Discovery.jsx';

vi.mock('../services/api.js', () => ({
    matches: {
        reverseDiscovery: vi.fn(),
    },
    wishlist: {
        add: vi.fn(),
    },
}));

import { matches, wishlist } from '../services/api.js';

// A partner fixture with two offered books: one with an ISBN and one without
const partnerWithBooks = {
    user: { id: 'user-2', username: 'alice', avg_recent_rating: '4.5' },
    they_want: [
        { id: 'ub-1', book: { id: 'book-1', title: 'Dune', authors: ['Frank Herbert'] } },
    ],
    they_offer: [
        {
            id: 'ub-2',
            book: {
                id: 'book-2',
                title: 'Foundation',
                authors: ['Isaac Asimov'],
                isbn_13: '9780553293357',
            },
        },
        {
            id: 'ub-3',
            book: {
                id: 'book-3',
                title: 'No ISBN Book',
                authors: ['Some Author'],
                // intentionally no isbn fields
            },
        },
    ],
};

describe('Discovery page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('shows a loading spinner while fetching', () => {
        matches.reverseDiscovery.mockReturnValue(new Promise(() => {}));
        renderWithProviders(<Discovery />);
        expect(screen.getByText(/finding potential trade partners/i)).toBeInTheDocument();
    });

    it('shows an error message when the fetch fails', async () => {
        matches.reverseDiscovery.mockRejectedValue(new Error('Network error'));
        renderWithProviders(<Discovery />);
        expect(await screen.findByText(/network error/i)).toBeInTheDocument();
    });

    it('shows the empty state when no partners are returned', async () => {
        matches.reverseDiscovery.mockResolvedValue({ data: [] });
        renderWithProviders(<Discovery />);
        expect(await screen.findByText(/no potential partners found yet/i)).toBeInTheDocument();
        expect(screen.getByRole('link', { name: /manage my books/i })).toBeInTheDocument();
    });

    it('renders partner username and rating when partners are returned', async () => {
        matches.reverseDiscovery.mockResolvedValue({ data: [partnerWithBooks] });
        renderWithProviders(<Discovery />);
        expect(await screen.findByText('@alice')).toBeInTheDocument();
        expect(screen.getByText(/4\.5/)).toBeInTheDocument();
    });

    it('renders the "Wants from you" badge for the partner', async () => {
        matches.reverseDiscovery.mockResolvedValue({ data: [partnerWithBooks] });
        renderWithProviders(<Discovery />);
        expect(await screen.findByText('Dune')).toBeInTheDocument();
    });

    it('renders offered book titles', async () => {
        matches.reverseDiscovery.mockResolvedValue({ data: [partnerWithBooks] });
        renderWithProviders(<Discovery />);
        expect(await screen.findByText('Foundation')).toBeInTheDocument();
        expect(screen.getByText('No ISBN Book')).toBeInTheDocument();
    });

    it('renders a profile link for the partner', async () => {
        matches.reverseDiscovery.mockResolvedValue({ data: [partnerWithBooks] });
        renderWithProviders(<Discovery />);
        const profileLink = await screen.findByRole('link', { name: '@alice' });
        expect(profileLink).toHaveAttribute('href', '/profile/user-2');
    });

    it('calls wishlist.add with the correct isbn when "I want this" is clicked', async () => {
        matches.reverseDiscovery.mockResolvedValue({ data: [partnerWithBooks] });
        wishlist.add.mockResolvedValue({ data: {} });
        renderWithProviders(<Discovery />);

        const buttons = await screen.findAllByRole('button', { name: /i want this/i });
        await userEvent.click(buttons[0]);

        await waitFor(() => {
            expect(wishlist.add).toHaveBeenCalledWith({ isbn: '9780553293357' });
        });
    });

    it('removes the "I want this" button after successfully adding a book to wishlist', async () => {
        matches.reverseDiscovery.mockResolvedValue({ data: [partnerWithBooks] });
        wishlist.add.mockResolvedValue({ data: {} });
        renderWithProviders(<Discovery />);

        const buttons = await screen.findAllByRole('button', { name: /i want this/i });
        // There is exactly one "I want this" button (the book with ISBN)
        expect(buttons).toHaveLength(1);
        await userEvent.click(buttons[0]);

        // After adding, canAddToWishlist is false so BookCard renders no button for that book
        await waitFor(() => {
            expect(screen.queryByRole('button', { name: /i want this/i })).not.toBeInTheDocument();
        });
    });

    it('renders no action button for books without an ISBN', async () => {
        matches.reverseDiscovery.mockResolvedValue({ data: [partnerWithBooks] });
        renderWithProviders(<Discovery />);

        // Wait for the page to render
        await screen.findByText('No ISBN Book');

        // Only the book with an ISBN gets an "I want this" button
        const actionButtons = screen.getAllByRole('button', { name: /i want this/i });
        expect(actionButtons).toHaveLength(1);
        // No action button for the no-ISBN book — wishlist.add must never be called
        expect(wishlist.add).not.toHaveBeenCalled();
    });
});
