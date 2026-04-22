import React from 'react';
import { screen } from '@testing-library/react';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Wishlist from './Wishlist.jsx';

vi.mock('../services/api.js', () => ({
    wishlist: {
        list: vi.fn(),
        add: vi.fn(),
        update: vi.fn(),
        remove: vi.fn(),
    },
}));

import { wishlist } from '../services/api.js';

describe('Wishlist page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders wishlist books from the current API shape', async () => {
        wishlist.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'wish-1',
                        min_condition: 'good',
                        is_active: true,
                        created_at: '2026-04-20T12:00:00Z',
                        book: {
                            id: 'book-1',
                            title: 'Kindred',
                            authors: ['Octavia E. Butler'],
                            isbn_13: '9780807083697',
                            physical_format: 'Paperback',
                            cover_image_url: 'https://example.com/kindred.jpg',
                        },
                    },
                ],
            },
        });

        renderWithProviders(<Wishlist />);

        expect(await screen.findByText('Kindred')).toBeInTheDocument();
        expect(screen.getByText('Octavia E. Butler')).toBeInTheDocument();
        expect(screen.getByText(/9780807083697/)).toBeInTheDocument();
        expect(screen.getByText(/Paperback/)).toBeInTheDocument();
        expect(screen.getByAltText('Kindred')).toHaveAttribute(
            'src',
            'https://example.com/kindred.jpg'
        );
    });
});