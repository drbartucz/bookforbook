import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
    users: {
        verifyAddress: vi.fn(),
    },
}));

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
                <button
                    type="button"
                    onClick={() =>
                        onBookFound({
                            id: 'book-lookup-isbn10',
                            isbn_10: value,
                            // no isbn_13, no title — exercises line 109 and 120 fallback branches
                        })
                    }
                >
                    Mock Lookup ISBN10
                </button>
            </div>
        );
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

    it('shows address prompt popup after first offer listing', async () => {
        myBooks.list.mockResolvedValue({
            data: { count: 0, results: [] },
        });
        myBooks.add.mockResolvedValue({
            data: {},
            headers: { 'x-address-prompt': 'add_now' },
        });

        renderWithProviders(<MyBooks />);

        await userEvent.click(await screen.findByRole('button', { name: '+ Add Book' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));
        await userEvent.click(screen.getByRole('button', { name: 'Add to My Books' }));

        expect(
            await screen.findByRole('heading', { name: 'Would you like to add your address now?' })
        ).toBeInTheDocument();
    });

    it('shows loading spinner while fetching', () => {
        myBooks.list.mockReturnValue(new Promise(() => {}));
        renderWithProviders(<MyBooks />);
        expect(document.querySelector('[class*="spinner"]') || document.querySelector('[class*="loading"]')).toBeTruthy();
    });

    it('shows error message when fetch fails', async () => {
        myBooks.list.mockRejectedValue(new Error('Network error'));
        renderWithProviders(<MyBooks />);
        expect(await screen.findByText(/network error/i)).toBeInTheDocument();
    });

    it('shows empty state with "Add your first book" button', async () => {
        myBooks.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<MyBooks />);
        expect(await screen.findByText(/no books yet/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /add your first book/i })).toBeInTheDocument();
    });

    it('opens edit form and cancels', async () => {
        myBooks.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'user-book-2',
                        condition: 'good',
                        status: 'available',
                        created_at: '2026-04-20T12:00:00Z',
                        book: { id: 'book-2', title: 'Dune', authors: ['Frank Herbert'], isbn_13: '9780441013593' },
                    },
                ],
            },
        });
        renderWithProviders(<MyBooks />);
        const editBtn = await screen.findByRole('button', { name: 'Edit' });
        await userEvent.click(editBtn);
        expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument();
        await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
        expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument();
    });

    it('saves edited condition', async () => {
        myBooks.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'user-book-3',
                        condition: 'good',
                        status: 'available',
                        created_at: '2026-04-20T12:00:00Z',
                        book: { id: 'book-3', title: 'Foundation', authors: ['Isaac Asimov'], isbn_13: '9780553293357' },
                    },
                ],
            },
        });
        myBooks.update.mockResolvedValue({ data: {} });
        renderWithProviders(<MyBooks />);
        const editBtn = await screen.findByRole('button', { name: 'Edit' });
        await userEvent.click(editBtn);
        await userEvent.click(screen.getByRole('button', { name: 'Save' }));
        await waitFor(() => expect(myBooks.update).toHaveBeenCalledWith('user-book-3', expect.any(Object)));
    });

    it('removes a book', async () => {
        vi.spyOn(window, 'confirm').mockReturnValue(true);
        myBooks.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'user-book-4',
                        condition: 'good',
                        status: 'available',
                        created_at: '2026-04-20T12:00:00Z',
                        book: { id: 'book-4', title: 'Ender\'s Game', authors: ['Orson Scott Card'], isbn_13: '9780812550702' },
                    },
                ],
            },
        });
        myBooks.remove.mockResolvedValue({ data: {} });
        renderWithProviders(<MyBooks />);
        const removeBtn = await screen.findByRole('button', { name: 'Remove' });
        await userEvent.click(removeBtn);
        await waitFor(() => expect(myBooks.remove).toHaveBeenCalledWith('user-book-4'));
        window.confirm.mockRestore();
    });

    it('changes sort-by selection in empty state', async () => {
        myBooks.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<MyBooks />);
        await screen.findByText(/no books yet/i);
        await userEvent.selectOptions(screen.getAllByRole('combobox')[0], 'title');
        await waitFor(() => expect(myBooks.list).toHaveBeenCalledWith(expect.objectContaining({ sort_by: 'title' })));
    });

    it('shows confirmation dialog when adding a duplicate book', async () => {
        vi.spyOn(window, 'confirm').mockReturnValue(false);
        myBooks.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'user-book-dup',
                        condition: 'good',
                        status: 'available',
                        created_at: '2026-04-20T12:00:00Z',
                        book: { id: 'book-dup', title: 'Dupe Book', isbn_13: '9780393081084' },
                    },
                ],
            },
        });
        renderWithProviders(<MyBooks />);
        await screen.findByText('Dupe Book');
        await userEvent.click(screen.getByRole('button', { name: '+ Add Book' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));
        await userEvent.click(screen.getByRole('button', { name: 'Add to My Books' }));
        expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('already have'));
        expect(myBooks.add).not.toHaveBeenCalled();
        window.confirm.mockRestore();
    });

    it('changes sort by selection', async () => {
        myBooks.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'user-book-5',
                        condition: 'good',
                        status: 'available',
                        created_at: '2026-04-20T12:00:00Z',
                        book: { id: 'book-5', title: 'Brave New World', authors: ['Huxley'], isbn_13: '9780060850524' },
                    },
                ],
            },
        });
        renderWithProviders(<MyBooks />);
        await screen.findByText('Brave New World');
        // Selects are unlabeled via htmlFor — get all comboboxes
        const selects = screen.getAllByRole('combobox');
        // First select is Sort by, second is Order
        await userEvent.selectOptions(selects[0], 'title');
        await waitFor(() => expect(myBooks.list).toHaveBeenCalledWith(expect.objectContaining({ sort_by: 'title' })));
    });

    it('changes sort order selection in populated state', async () => {
        myBooks.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'user-book-6',
                        condition: 'good',
                        status: 'available',
                        created_at: '2026-04-20T12:00:00Z',
                        book: { id: 'book-6', title: '1984', authors: ['Orwell'], isbn_13: '9780451524935' },
                    },
                ],
            },
        });
        renderWithProviders(<MyBooks />);
        await screen.findByText('1984');
        const selects = screen.getAllByRole('combobox');
        await userEvent.selectOptions(selects[1], 'asc');
        await waitFor(() => expect(myBooks.list).toHaveBeenCalledWith(expect.objectContaining({ sort_order: 'asc' })));
    });

    it('changes sort order selection in empty state', async () => {
        myBooks.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<MyBooks />);
        await screen.findByText(/no books yet/i);
        const selects = screen.getAllByRole('combobox');
        await userEvent.selectOptions(selects[1], 'asc');
        await waitFor(() => expect(myBooks.list).toHaveBeenCalledWith(expect.objectContaining({ sort_order: 'asc' })));
    });

    it('shows error when add book API fails', async () => {
        myBooks.list.mockResolvedValue({ data: { count: 0, results: [] } });
        myBooks.add.mockRejectedValueOnce({
            response: { data: { detail: 'That book is already in a trade.' } },
        });
        renderWithProviders(<MyBooks />);
        await userEvent.click(await screen.findByRole('button', { name: '+ Add Book' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));
        await userEvent.click(screen.getByRole('button', { name: 'Add to My Books' }));
        await waitFor(() => expect(screen.getByText('That book is already in a trade.')).toBeInTheDocument());
    });

    it('shows generic fallback when add book API fails without detail', async () => {
        myBooks.list.mockResolvedValue({ data: { count: 0, results: [] } });
        myBooks.add.mockRejectedValueOnce({ response: { data: {} } });
        renderWithProviders(<MyBooks />);
        await userEvent.click(await screen.findByRole('button', { name: '+ Add Book' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));
        await userEvent.click(screen.getByRole('button', { name: 'Add to My Books' }));
        await waitFor(() => expect(screen.getByText('Failed to add book. Please try again.')).toBeInTheDocument());
    });

    it('shows "copies" plural in confirm dialog when 2 or more copies exist', async () => {
        vi.spyOn(window, 'confirm').mockReturnValue(false);
        myBooks.list.mockResolvedValue({
            data: {
                count: 2,
                results: [
                    { id: 'user-book-dup1', condition: 'good', status: 'available', created_at: '2026-04-20T12:00:00Z', book: { id: 'book-dup1', title: 'Dupe Book', isbn_13: '9780393081084' } },
                    { id: 'user-book-dup2', condition: 'good', status: 'available', created_at: '2026-04-20T12:00:00Z', book: { id: 'book-dup2', title: 'Dupe Book', isbn_13: '9780393081084' } },
                ],
            },
        });
        renderWithProviders(<MyBooks />);
        const dupeBooks = await screen.findAllByText('Dupe Book');
        expect(dupeBooks.length).toBeGreaterThan(0);
        await userEvent.click(screen.getByRole('button', { name: '+ Add Book' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));
        await userEvent.click(screen.getByRole('button', { name: 'Add to My Books' }));
        expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('copies'));
        window.confirm.mockRestore();
    });

    it('renders book with unknown status using raw status as fallback label', async () => {
        myBooks.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    { id: 'user-book-unknown', condition: 'good', status: 'custom_status', created_at: '2026-04-20T12:00:00Z', book: { id: 'book-u', title: 'Status Book', authors: [], isbn_13: '9780553293357' } },
                ],
            },
        });
        renderWithProviders(<MyBooks />);
        expect(await screen.findByText('Status Book')).toBeInTheDocument();
        expect(screen.getByText('custom_status')).toBeInTheDocument();
    });

    it('shows non_field_errors when add book API fails with that field', async () => {
        myBooks.list.mockResolvedValue({ data: { count: 0, results: [] } });
        myBooks.add.mockRejectedValueOnce({
            response: { data: { non_field_errors: ['Duplicate entry.', 'Already listed.'] } },
        });
        renderWithProviders(<MyBooks />);
        await userEvent.click(await screen.findByRole('button', { name: '+ Add Book' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));
        await userEvent.click(screen.getByRole('button', { name: 'Add to My Books' }));
        // no 'detail' → non_field_errors.join(' ') used (covers line 72)
        await waitFor(() => expect(screen.getByText('Duplicate entry. Already listed.')).toBeInTheDocument());
    });

    it('uses isbn_10 and "this book" fallback when foundBook has no isbn_13 or title', async () => {
        vi.spyOn(window, 'confirm').mockReturnValue(false);
        myBooks.list.mockResolvedValue({
            data: {
                count: 1,
                results: [{
                    id: 'user-book-isbn10',
                    condition: 'good',
                    status: 'available',
                    created_at: '2026-04-20T12:00:00Z',
                    book: { id: 'bk', title: 'ISBN10 Book', isbn_13: null, isbn_10: '0393081087' },
                }],
            },
        });
        renderWithProviders(<MyBooks />);
        await screen.findByText('ISBN10 Book');
        await userEvent.click(screen.getByRole('button', { name: '+ Add Book' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '0393081087');
        // Use the isbn_10-only mock button: onBookFound({ id, isbn_10 }) — no isbn_13, no title
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup ISBN10' }));
        await userEvent.click(screen.getByRole('button', { name: 'Add to My Books' }));
        // targetIsbn = foundBook.isbn_13 || foundBook.isbn_10 (line 109) = undefined || '0393081087'
        // title = foundBook.title || 'this book' (line 120) = undefined || 'this book'
        expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('this book'));
        window.confirm.mockRestore();
    });

    it('renders a flat item (no nested book property) using item itself as book data', async () => {
        myBooks.list.mockResolvedValue({
            data: {
                count: 1,
                results: [{
                    id: 'flat-1',
                    condition: 'good',
                    status: 'available',
                    created_at: '2026-04-20T12:00:00Z',
                    // No 'book' property — item.book is undefined → item.book ?? item → item (covers line 296)
                    title: 'Flat Book Title',
                    authors: ['Flat Author'],
                    isbn_13: '9780441013593',
                }],
            },
        });
        renderWithProviders(<MyBooks />);
        expect(await screen.findByText('Flat Book Title')).toBeInTheDocument();
        expect(screen.getByText('Flat Author')).toBeInTheDocument();
    });

    it('uses isbn_10 for duplicate detection when isbn_13 is absent', async () => {
        vi.spyOn(window, 'confirm').mockReturnValue(false);
        myBooks.list.mockResolvedValue({
            data: {
                count: 1,
                results: [{
                    id: 'user-book-isbn10',
                    condition: 'good',
                    status: 'available',
                    created_at: '2026-04-20T12:00:00Z',
                    book: { id: 'book-isbn10', title: 'ISBN10 Book', isbn_13: null, isbn_10: '0393081087' },
                }],
            },
        });
        renderWithProviders(<MyBooks />);
        await screen.findByText('ISBN10 Book');
        await userEvent.click(screen.getByRole('button', { name: '+ Add Book' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '0393081087');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));
        await userEvent.click(screen.getByRole('button', { name: 'Add to My Books' }));
        // item.book.isbn_13 is null → || item.book.isbn_10 = '0393081087' (covers line 114 right branch)
        expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('already have'));
        window.confirm.mockRestore();
    });

    it('shows validation error when submitting add form with empty ISBN', async () => {
        myBooks.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<MyBooks />);
        await userEvent.click(await screen.findByRole('button', { name: '+ Add Book' }));
        fireEvent.submit(document.querySelector('form'));
        expect(screen.getByText('Please enter an ISBN.')).toBeInTheDocument();
    });

    it('skips cache entries without results when checking duplicates (covers if (!pageData?.results) continue at line 112)', async () => {
        // When list returns null data, the cache entry has pageData = null, triggering the continue branch
        myBooks.list.mockResolvedValue({ data: null });
        myBooks.add.mockResolvedValue({ data: {} });
        renderWithProviders(<MyBooks />);
        // With null data, books = [] → empty state renders
        await userEvent.click(await screen.findByRole('button', { name: /add your first book/i }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));
        await userEvent.click(screen.getByRole('button', { name: 'Add to My Books' }));
        // Cache entry has pageData = null → !null?.results = true → continue fires
        await waitFor(() => expect(myBooks.add).toHaveBeenCalled());
    });

    it('shows validation error when submitting add form without looking up book', async () => {
        myBooks.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<MyBooks />);
        await userEvent.click(await screen.findByRole('button', { name: '+ Add Book' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        // Do NOT click Mock Lookup — foundBook is still null
        fireEvent.submit(document.querySelector('form'));
        expect(screen.getByText('Please look up the ISBN first.')).toBeInTheDocument();
    });

    it('covers add-form condition select onChange (line 188)', async () => {
        myBooks.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<MyBooks />);
        await userEvent.click(await screen.findByRole('button', { name: '+ Add Book' }));
        // Change the condition select in the add form — covers onChange at line 188
        const conditionSelect = screen.getByRole('combobox', { name: /condition/i });
        await userEvent.selectOptions(conditionSelect, 'acceptable');
        expect(conditionSelect).toHaveValue('acceptable');
    });

    it('covers edit-form condition select onChange (line 334)', async () => {
        myBooks.list.mockResolvedValue({
            data: {
                count: 1,
                results: [{
                    id: 'ub-edit-cond',
                    condition: 'good',
                    status: 'available',
                    created_at: '2026-04-20T12:00:00Z',
                    book: { id: 'bk-edit', title: 'Edit Condition Book', authors: ['Author'], isbn_13: '9780553293357' },
                }],
            },
        });
        renderWithProviders(<MyBooks />);
        await userEvent.click(await screen.findByRole('button', { name: 'Edit' }));
        // Change condition in the edit form — covers onChange at line 334
        const editSelect = screen.getByRole('combobox');
        await userEvent.selectOptions(editSelect, 'very_good');
        expect(editSelect).toHaveValue('very_good');
    });

    it('covers AddressPromptModal onClose callback (line 386) by clicking "Not now"', async () => {
        myBooks.list.mockResolvedValue({ data: { count: 0, results: [] } });
        myBooks.add.mockResolvedValue({
            data: {},
            headers: { 'x-address-prompt': 'add_now' },
        });
        renderWithProviders(<MyBooks />);
        await userEvent.click(await screen.findByRole('button', { name: '+ Add Book' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));
        await userEvent.click(screen.getByRole('button', { name: 'Add to My Books' }));
        await screen.findByRole('heading', { name: 'Would you like to add your address now?' });
        // Dismiss the modal — covers onClose={() => setShowAddressPrompt(false)} at line 386
        await userEvent.click(screen.getByRole('button', { name: /not now/i }));
        expect(screen.queryByRole('heading', { name: /would you like to add your address/i })).not.toBeInTheDocument();
    });
});