import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import ISBNInput from './ISBNInput.jsx';

vi.mock('../../services/api.js', () => ({
    books: {
        lookupISBN: vi.fn(),
    },
}));

describe('ISBNInput', () => {
    it('shows external validation error only after blur', async () => {
        const onBookFound = vi.fn();
        const onChange = vi.fn();

        render(
            <ISBNInput
                value="123"
                onChange={onChange}
                onBookFound={onBookFound}
                error="ISBN must be 10 or 13 digits."
            />
        );

        expect(screen.queryByText('ISBN must be 10 or 13 digits.')).not.toBeInTheDocument();
        await userEvent.click(screen.getByLabelText('ISBN'));
        await userEvent.tab();
        expect(screen.getByText('ISBN must be 10 or 13 digits.')).toBeInTheDocument();
    });

    it('renders preview data from the current lookup response shape', async () => {
        const onBookFound = vi.fn();
        const onChange = vi.fn();
        const { books } = await import('../../services/api.js');

        books.lookupISBN.mockResolvedValue({
            data: {
                title: 'The Food Lab',
                authors: ['J. Kenji Lopez-Alt'],
                publish_year: 2015,
                cover_image_url: 'https://example.com/foodlab.jpg',
            },
        });

        render(
            <ISBNInput
                value="9780393081084"
                onChange={onChange}
                onBookFound={onBookFound}
            />
        );

        await userEvent.click(screen.getByRole('button', { name: /lookup/i }));

        expect(await screen.findByText('The Food Lab')).toBeInTheDocument();
        expect(screen.getByText('J. Kenji Lopez-Alt')).toBeInTheDocument();
        expect(screen.getByText('2015')).toBeInTheDocument();
        expect(screen.getByAltText('Book cover')).toHaveAttribute(
            'src',
            'https://example.com/foodlab.jpg'
        );
        expect(onBookFound).toHaveBeenCalledWith(
            expect.objectContaining({
                title: 'The Food Lab',
                authors: ['J. Kenji Lopez-Alt'],
                publish_year: 2015,
                cover_image_url: 'https://example.com/foodlab.jpg',
            })
        );
    });
});