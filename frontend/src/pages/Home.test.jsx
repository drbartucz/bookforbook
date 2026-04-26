import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Home from './Home.jsx';

vi.mock('../services/api.js', () => ({
    browse: {
        available: vi.fn(),
    },
    wishlist: {
        add: vi.fn(),
    },
}));

vi.mock('../hooks/useAuth.js', () => ({
    default: vi.fn(),
}));

vi.mock('../hooks/useDebounce.js', () => ({
    default: vi.fn((value) => value),
}));

import { browse, wishlist } from '../services/api.js';
import useAuth from '../hooks/useAuth.js';

describe('Home page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders books from the current API shape and adds wishlist items using isbn_13', async () => {
        useAuth.mockReturnValue({
            isAuthenticated: true,
        });

        browse.available.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'book-1',
                        title: 'The Left Hand of Darkness',
                        authors: ['Ursula K. Le Guin'],
                        isbn_13: '9780441478125',
                        cover_image_url: 'https://example.com/lefthand.jpg',
                        condition: 'good',
                        copy_count: 1,
                    },
                ],
            },
        });
        wishlist.add.mockResolvedValue({ data: {} });

        renderWithProviders(<Home />);

        expect(await screen.findByText('The Left Hand of Darkness')).toBeInTheDocument();
        expect(screen.getByText('Ursula K. Le Guin')).toBeInTheDocument();
        expect(screen.getByText(/9780441478125/)).toBeInTheDocument();
        expect(screen.getByAltText('Cover of The Left Hand of Darkness')).toHaveAttribute(
            'src',
            'https://example.com/lefthand.jpg'
        );

        await userEvent.click(screen.getByRole('button', { name: 'Want this' }));

        await waitFor(() => {
            expect(wishlist.add).toHaveBeenCalledWith({ isbn: '9780441478125' });
        });
    });

    it('shows error message when browse fetch fails', async () => {
        useAuth.mockReturnValue({ isAuthenticated: false });
        browse.available.mockRejectedValue(new Error('Network error'));
        renderWithProviders(<Home />);
        expect(await screen.findByText(/network error/i)).toBeInTheDocument();
    });

    it('shows empty state subtitle for authenticated user with no books', async () => {
        useAuth.mockReturnValue({ isAuthenticated: true });
        browse.available.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Home />);
        expect(await screen.findByText(/be the first to add a book/i)).toBeInTheDocument();
    });

    it('shows "Start trading" link for unauthenticated users on empty state', async () => {
        useAuth.mockReturnValue({ isAuthenticated: false });
        browse.available.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Home />);
        await screen.findByText(/be the first to add a book/i);
        expect(screen.getByRole('link', { name: /start trading/i })).toBeInTheDocument();
    });

    it('shows "X books available" count header', async () => {
        useAuth.mockReturnValue({ isAuthenticated: false });
        browse.available.mockResolvedValue({
            data: {
                count: 3,
                results: [
                    { id: 'b1', title: 'Book One',   authors: ['A'], isbn_13: '1111111111111', cover_image_url: null, copy_count: 1 },
                    { id: 'b2', title: 'Book Two',   authors: ['B'], isbn_13: '2222222222222', cover_image_url: null, copy_count: 1 },
                    { id: 'b3', title: 'Book Three', authors: ['C'], isbn_13: '3333333333333', cover_image_url: null, copy_count: 1 },
                ],
            },
        });
        renderWithProviders(<Home />);
        expect(await screen.findByText(/3 books available/i)).toBeInTheDocument();
    });

    it('calls handleSearchChange when search input is updated', async () => {
        useAuth.mockReturnValue({ isAuthenticated: false });
        browse.available.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Home />);
        await screen.findByText(/be the first to add a book/i);
        await userEvent.type(screen.getByLabelText('Search books'), 'dune');
        await waitFor(() => {
            expect(browse.available).toHaveBeenCalledWith(expect.objectContaining({ q: 'dune' }));
        });
    });

    it('shows "Try adjusting" subtitle when search is active but no books found', async () => {
        useAuth.mockReturnValue({ isAuthenticated: false });
        browse.available.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Home />);
        await screen.findByText(/be the first to add a book/i);
        await userEvent.type(screen.getByLabelText('Search books'), 'x');
        await waitFor(() => {
            expect(screen.getByText(/try adjusting your search or filters/i)).toBeInTheDocument();
        });
    });

    it('renders a book returned directly by the API (flat shape)', async () => {
        useAuth.mockReturnValue({ isAuthenticated: false });
        browse.available.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'book-flat',
                        title: 'Flat Book Title',
                        authors: ['Flat Author'],
                        isbn_13: '9780000000001',
                        cover_image_url: null,
                        copy_count: 1,
                    },
                ],
            },
        });
        renderWithProviders(<Home />);
        expect(await screen.findByText('Flat Book Title')).toBeInTheDocument();
        expect(screen.getByText('Flat Author')).toBeInTheDocument();
    });

    it('shows copy count badge when the API reports multiple copies', async () => {
        useAuth.mockReturnValue({ isAuthenticated: false });
        browse.available.mockResolvedValue({
            data: {
                count: 2,
                results: [
                    { id: 'b1', title: 'Dune',       authors: ['Herbert'], isbn_13: '9780441013593', condition: 'very_good', copy_count: 3 },
                    { id: 'b2', title: 'Foundation',  authors: ['Asimov'],  isbn_13: '9780553293357', condition: 'good',      copy_count: 1 },
                ],
            },
        });
        renderWithProviders(<Home />);
        await screen.findByText('Dune');
        expect(screen.getByText('3 copies')).toBeInTheDocument();
        expect(screen.getByText('Foundation')).toBeInTheDocument();
        expect(screen.queryByText('1 copies')).not.toBeInTheDocument();
    });

    it('calls handleConditionChange when condition filter changes', async () => {
        useAuth.mockReturnValue({ isAuthenticated: false });
        browse.available.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Home />);
        await screen.findByText(/be the first to add a book/i);
        await userEvent.selectOptions(screen.getByLabelText('Filter by condition'), 'good');
        await waitFor(() => {
            expect(browse.available).toHaveBeenCalledWith(expect.objectContaining({ condition: 'good' }));
        });
    });
});