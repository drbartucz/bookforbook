import React from 'react';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Wishlist from './Wishlist.jsx';

vi.mock('../components/common/ISBNInput.jsx', () => ({
    default: function MockISBNInput({ value, onChange, onBookFound }) {
        return (
            <div>
                <input
                    aria-label="ISBN"
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                />
                <button
                    type="button"
                    onClick={() =>
                        onBookFound({
                            id: 'book-lookup-1',
                            title: 'Lookup Book',
                            isbn_13: value,
                        })
                    }
                >
                    Mock Lookup
                </button>
            </div>
        );
    },
}));

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

    it('submits custom edition preferences when adding a wishlist item', async () => {
        wishlist.list.mockResolvedValue({
            data: { count: 0, results: [] },
        });
        wishlist.add.mockResolvedValue({ data: {} });

        renderWithProviders(<Wishlist />);

        await userEvent.click(await screen.findByRole('button', { name: '+ Add to Wishlist' }));

        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));

        await userEvent.selectOptions(
            screen.getByLabelText('Match flexibility'),
            'custom'
        );
        await userEvent.click(screen.getByLabelText('Include translations'));
        await userEvent.click(screen.getByRole('button', { name: 'Hardcover' }));
        await userEvent.click(screen.getByRole('button', { name: 'Paperback' }));

        await userEvent.click(screen.getByRole('button', { name: 'Add to Wishlist' }));

        expect(wishlist.add).toHaveBeenCalledWith(
            expect.objectContaining({
                isbn: '9780393081084',
                edition_preference: 'custom',
                allow_translations: true,
                exclude_abridged: true,
                format_preferences: ['hardcover', 'paperback'],
            })
        );
    });
});