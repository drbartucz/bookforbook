import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import ISBNInput from './ISBNInput.jsx';

vi.mock('../../services/api.js', () => ({
    books: {
        lookupISBN: vi.fn(),
        fromImage: vi.fn(),
    },
}));

vi.mock('../../utils/isbnDetect.js', () => ({
    detectISBNFromFile: vi.fn(),
}));

function deferred() {
    let resolve;
    let reject;
    const promise = new Promise((res, rej) => {
        resolve = res;
        reject = rej;
    });
    return { promise, resolve, reject };
}

beforeEach(() => {
    vi.restoreAllMocks();
    if (!URL.createObjectURL) {
        URL.createObjectURL = () => 'blob:preview';
    }
    if (!URL.revokeObjectURL) {
        URL.revokeObjectURL = () => { };
    }
    vi.spyOn(URL, 'createObjectURL').mockImplementation(() => 'blob:preview');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => { });
});

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

        await userEvent.click(screen.getByRole('button', { name: /look\s*up/i }));

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

        await userEvent.click(screen.getByRole('button', { name: /look\s*up/i }));

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
        await userEvent.click(screen.getByRole('button', { name: /look\s*up/i }));

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

        await userEvent.click(screen.getByRole('button', { name: /look\s*up/i }));

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

        await userEvent.click(screen.getByRole('button', { name: /look\s*up/i }));

        expect(await screen.findByText('Book not found for this ISBN.')).toBeInTheDocument();
    });

    it('returns early from handleLookup when isbn is empty after stripping dashes (covers line 42)', async () => {
        const onBookFound = vi.fn();
        const onChange = vi.fn();
        const { books } = await import('../../services/api.js');
        books.lookupISBN.mockClear();

        // A single dash strips to empty string after replace(/[\s-]/g, '')
        render(<ISBNInput value="-" onChange={onChange} onBookFound={onBookFound} />);
        await userEvent.click(screen.getByRole('button', { name: /look\s*up/i }));

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

        await userEvent.click(screen.getByRole('button', { name: /look\s*up/i }));
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

        await userEvent.click(screen.getByRole('button', { name: /look\s*up/i }));

        // Should strip whitespace and call API with clean ISBN
        expect(books.lookupISBN).toHaveBeenCalledWith('9780393081084');
        expect(await screen.findByText('Dirty Input Book')).toBeInTheDocument();
    });

    it('performs a successful lookup when value uses spaces as separators (issue #44)', async () => {
        const onBookFound = vi.fn();
        const onChange = vi.fn();
        const { books } = await import('../../services/api.js');

        books.lookupISBN.mockResolvedValue({
            data: { title: 'Space Separated Book', authors: ['Author'], publish_year: 2022 },
        });

        // ISBN entered with spaces as separators, e.g. "978 0 545 01022 1"
        render(
            <ISBNInput value="978 0 545 01022 1" onChange={onChange} onBookFound={onBookFound} />
        );

        await userEvent.click(screen.getByRole('button', { name: /look\s*up/i }));

        // Should strip internal spaces and call API with clean ISBN
        expect(books.lookupISBN).toHaveBeenCalledWith('9780545010221');
        expect(await screen.findByText('Space Separated Book')).toBeInTheDocument();
    });

    it('test_rapid_uploads_only_latest_result_applies', async () => {
        const onBookFound = vi.fn();
        const onChange = vi.fn();
        const { books } = await import('../../services/api.js');
        const { detectISBNFromFile } = await import('../../utils/isbnDetect.js');

        const firstDetect = deferred();
        const secondDetect = deferred();
        const firstLookup = deferred();
        const secondLookup = deferred();

        detectISBNFromFile
            .mockImplementationOnce(() => firstDetect.promise)
            .mockImplementationOnce(() => secondDetect.promise);

        books.lookupISBN.mockImplementation((isbn) => (
            isbn === '2222222222' ? secondLookup.promise : firstLookup.promise
        ));

        render(
            <ISBNInput value="" onChange={onChange} onBookFound={onBookFound} />
        );

        const fileInput = document.querySelector('input[type="file"]');
        const firstFile = new File(['a'], 'first.png', { type: 'image/png' });
        const secondFile = new File(['b'], 'second.png', { type: 'image/png' });

        fireEvent.change(fileInput, { target: { files: [firstFile] } });
        fireEvent.change(fileInput, { target: { files: [secondFile] } });

        expect(detectISBNFromFile).toHaveBeenCalledTimes(2);

        await act(async () => {
            secondDetect.resolve({ status: 'found', isbn: '2222222222' });
            await Promise.resolve();
        });

        await waitFor(() => {
            expect(books.lookupISBN).toHaveBeenCalledWith('2222222222');
        });

        await act(async () => {
            secondLookup.resolve({
                data: { title: 'Second Book', authors: ['Second Author'], publish_year: 2021 },
            });
            await Promise.resolve();
        });

        expect(await screen.findByText('Second Book')).toBeInTheDocument();

        await act(async () => {
            firstDetect.resolve({ status: 'found', isbn: '1111111111' });
            await Promise.resolve();
            firstLookup.resolve({
                data: { title: 'First Book', authors: ['First Author'], publish_year: 2020 },
            });
            await Promise.resolve();
        });

        expect(screen.getByText('Second Book')).toBeInTheDocument();
        expect(screen.queryByText('First Book')).not.toBeInTheDocument();
        expect(onBookFound).toHaveBeenLastCalledWith(
            expect.objectContaining({ title: 'Second Book' })
        );
    });

    it('test_stale_lookup_error_does_not_override_latest_success', async () => {
        const onBookFound = vi.fn();
        const onChange = vi.fn();
        const { books } = await import('../../services/api.js');
        const { detectISBNFromFile } = await import('../../utils/isbnDetect.js');

        const firstLookup = deferred();

        detectISBNFromFile
            .mockResolvedValueOnce({ status: 'found', isbn: '1111111111' })
            .mockResolvedValueOnce({ status: 'found', isbn: '2222222222' });

        books.lookupISBN
            .mockImplementationOnce(() => firstLookup.promise)
            .mockResolvedValueOnce({
                data: { title: 'Latest Success', authors: ['Author'], publish_year: 2024 },
            });

        render(<ISBNInput value="" onChange={onChange} onBookFound={onBookFound} />);

        const fileInput = document.querySelector('input[type="file"]');
        const firstFile = new File(['a'], 'first.png', { type: 'image/png' });
        const secondFile = new File(['b'], 'second.png', { type: 'image/png' });

        await userEvent.upload(fileInput, firstFile);
        await userEvent.upload(fileInput, secondFile);

        expect(await screen.findByText('Latest Success')).toBeInTheDocument();

        await act(async () => {
            firstLookup.reject({ response: { data: { detail: 'Old request failed' } } });
            await Promise.resolve();
        });

        expect(screen.getByText('Latest Success')).toBeInTheDocument();
        expect(screen.queryByText('Old request failed')).not.toBeInTheDocument();
        expect(onBookFound).toHaveBeenLastCalledWith(
            expect.objectContaining({ title: 'Latest Success' })
        );
    });

    it('test_scan_cleanup_resets_candidates_and_error_per_new_upload', async () => {
        const onBookFound = vi.fn();
        const onChange = vi.fn();
        const { books } = await import('../../services/api.js');
        const { detectISBNFromFile } = await import('../../utils/isbnDetect.js');

        detectISBNFromFile
            .mockResolvedValueOnce({ status: 'multiple', candidates: ['1234567890', '0987654321'] })
            .mockResolvedValueOnce({ status: 'not_found' });

        books.fromImage
            .mockResolvedValueOnce({ data: {} })
            .mockResolvedValueOnce({ data: {} });

        render(<ISBNInput value="" onChange={onChange} onBookFound={onBookFound} />);

        const fileInput = document.querySelector('input[type="file"]');
        const firstFile = new File(['a'], 'first.png', { type: 'image/png' });
        const secondFile = new File(['b'], 'second.png', { type: 'image/png' });

        await userEvent.upload(fileInput, firstFile);

        expect(await screen.findByText('Multiple ISBNs found — pick one:')).toBeInTheDocument();

        await userEvent.upload(fileInput, secondFile);

        expect(screen.queryByText('Multiple ISBNs found — pick one:')).not.toBeInTheDocument();
        expect(await screen.findByText('No ISBN found in image. Try a clearer photo or enter it manually.')).toBeInTheDocument();
    });
});