import React from 'react';
import { screen } from '@testing-library/react';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import MyBooks from './MyBooks.jsx';

vi.mock('../services/api.js', () => ({
    myBooks: {
        list: vi.fn(),
        add: vi.fn(),
        update: vi.fn(),
        remove: vi.fn(),
    },
}));

import { myBooks } from '../services/api.js';

describe('MyBooks page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders nested books from the current API shape', async () => {
        myBooks.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'user-book-1',
                        condition: 'very_good',
                        status: 'available',
                        created_at: '2026-04-20T12:00:00Z',
                        book: {
                            id: 'book-1',
                            title: 'The Food Lab',
                            authors: ['J. Kenji Lopez-Alt'],
                            isbn_13: '9780393081084',
                            physical_format: 'Hardcover',
                            cover_image_url: 'https://example.com/foodlab.jpg',
                        },
                    },
                ],
            },
        });

        renderWithProviders(<MyBooks />);

        expect(await screen.findByText('The Food Lab')).toBeInTheDocument();
        expect(screen.getByText('J. Kenji Lopez-Alt')).toBeInTheDocument();
        expect(screen.getByText(/9780393081084/)).toBeInTheDocument();
        expect(screen.getByText(/Hardcover/)).toBeInTheDocument();
        expect(screen.getByAltText('The Food Lab')).toHaveAttribute(
            'src',
            'https://example.com/foodlab.jpg'
        );
    });
});