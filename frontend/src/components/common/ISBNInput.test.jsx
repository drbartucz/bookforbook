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

    it('shows error and calls onBookFound(null) when lookup fails', async () => {
        const onBookFound = vi.fn();
        const onChange = vi.fn();
        const { books } = await import('../../services/api.js');

        books.lookupISBN.mockRejectedValue({
            response: { data: { detail: 'ISBN not found in database.' } },
        });

        render(
            <ISBNInput value="9999999999999" onChange={onChange} onBookFound={onBookFound} />
        );

        await userEvent.click(screen.getByRole('button', { name: /lookup/i }));

        expect(await screen.findByText('ISBN not found in database.')).toBeInTheDocument();
        expect(onBookFound).toHaveBeenCalledWith(null);
    });

    it('triggers lookup on Enter key press', async () => {
        const onBookFound = vi.fn();
        const onChange = vi.fn();
        const { books } = await import('../../services/api.js');

        books.lookupISBN.mockResolvedValue({
            data: { title: 'Enter Key Book', authors: ['Author'], publish_year: 2020 },
        });

        render(
            <ISBNInput value="9780393081084" onChange={onChange} onBookFound={onBookFound} />
        );

        await userEvent.type(screen.getByRole('textbox'), '{Enter}');
        expect(await screen.findByText('Enter Key Book')).toBeInTheDocument();
    });

    it('shows ISBN length error when entered ISBN has wrong length (covers lines 45-47)', async () => {
        const onBookFound = vi.fn();
        const onChange = vi.fn();

        render(
            <ISBNInput value="12345" onChange={onChange} onBookFound={onBookFound} />
        );

        // Click Lookup with a 5-digit ISBN — too short, so lines 45-47 fire
        await userEvent.click(screen.getByRole('button', { name: /lookup/i }));

        // hasLookupAttempted=true → shouldShowError=true → shows lookupError
        expect(screen.getByText('ISBN must be 10 or 13 digits.')).toBeInTheDocument();
    });

    it('shows message fallback error when lookup fails with message but no detail (covers line 62)', async () => {
        const onBookFound = vi.fn();
        const onChange = vi.fn();
        const { books } = await import('../../services/api.js');

        books.lookupISBN.mockRejectedValue({
            response: { data: { message: 'Book lookup service unavailable.' } },
        });

        render(
            <ISBNInput value="9780393081084" onChange={onChange} onBookFound={onBookFound} />
        );

        await userEvent.click(screen.getByRole('button', { name: /lookup/i }));

        expect(await screen.findByText('Book lookup service unavailable.')).toBeInTheDocument();
    });

    it('shows default fallback error when lookup fails with no detail or message (covers line 63)', async () => {
        const onBookFound = vi.fn();
        const onChange = vi.fn();
        const { books } = await import('../../services/api.js');

        books.lookupISBN.mockRejectedValue(new Error('Network error'));

        render(
            <ISBNInput value="9780393081084" onChange={onChange} onBookFound={onBookFound} />
        );

        await userEvent.click(screen.getByRole('button', { name: /lookup/i }));

        expect(await screen.findByText('Book not found for this ISBN.')).toBeInTheDocument();
    });

    it('returns early from handleLookup when isbn is empty after stripping dashes (covers line 42)', async () => {
        const onBookFound = vi.fn();
        const onChange = vi.fn();
        const { books } = await import('../../services/api.js');
        books.lookupISBN.mockClear();

        // A single dash strips to empty string after replace(/-/g, '')
        render(<ISBNInput value="-" onChange={onChange} onBookFound={onBookFound} />);
        await userEvent.click(screen.getByRole('button', { name: /lookup/i }));

        // isbn is empty after stripping → early return before calling lookupISBN
        expect(books.lookupISBN).not.toHaveBeenCalled();
    });

    it('clears lookup result when user changes ISBN after a successful lookup', async () => {
        const onBookFound = vi.fn();
        const onChange = vi.fn();
        const { books } = await import('../../services/api.js');

        books.lookupISBN.mockResolvedValue({
            data: { title: 'Found Book', authors: ['Author'], publish_year: 2020 },
        });

        render(
            <ISBNInput value="9780393081084" onChange={onChange} onBookFound={onBookFound} />
        );

        await userEvent.click(screen.getByRole('button', { name: /lookup/i }));
        expect(await screen.findByText('Found Book')).toBeInTheDocument();

        // Type a new character — should clear the result
        await userEvent.type(screen.getByRole('textbox'), '1');
        // onBookFound called again with null to clear
        expect(onBookFound).toHaveBeenLastCalledWith(null);
    });

    it('trims leading and trailing whitespace from pasted ISBN before passing to onChange', async () => {
        const onBookFound = vi.fn();
        const onChange = vi.fn();

        render(
            <ISBNInput value="" onChange={onChange} onBookFound={onBookFound} />
        );

        const input = screen.getByRole('textbox');
        await userEvent.type(input, '  9780393081084  ');

        // onChange should have been called with trimmed values, never with raw whitespace
        const calls = onChange.mock.calls.map(([v]) => v);
        expect(calls.every((v) => v === v.trim())).toBe(true);
    });

    it('performs a successful lookup when value has leading/trailing whitespace (issue #45)', async () => {
        const onBookFound = vi.fn();
        const onChange = vi.fn();
        const { books } = await import('../../services/api.js');

        books.lookupISBN.mockResolvedValue({
            data: { title: 'Dirty Input Book', authors: ['Author'], publish_year: 2021 },
        });

        // Simulate a value with leading spaces (e.g. copied from Amazon)
        render(
            <ISBNInput value="  9780393081084  " onChange={onChange} onBookFound={onBookFound} />
        );

        await userEvent.click(screen.getByRole('button', { name: /lookup/i }));

        // Should strip whitespace and call API with clean ISBN
        expect(books.lookupISBN).toHaveBeenCalledWith('9780393081084');
        expect(await screen.findByText('Dirty Input Book')).toBeInTheDocument();
    });
});