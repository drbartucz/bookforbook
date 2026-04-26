import React from 'react';
import { fireEvent, screen, waitFor } from '@testing-library/react';
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
    users: {
        verifyAddress: vi.fn(),
    },
}));

vi.mock('../hooks/useAuth.js', () => ({
    default: vi.fn(),
}));

import { wishlist } from '../services/api.js';
import useAuth from '../hooks/useAuth.js';

describe('Wishlist page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        useAuth.mockReturnValue({ user: null });
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

        expect(
            screen.getByRole('heading', { name: 'Would you also accept other editions?' })
        ).toBeInTheDocument();

        await userEvent.selectOptions(
            screen.getByLabelText('Edition matching'),
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

    it('closes edition popup on overlay click and Escape key', async () => {
        wishlist.list.mockResolvedValue({
            data: { count: 0, results: [] },
        });

        renderWithProviders(<Wishlist />);

        await userEvent.click(await screen.findByRole('button', { name: '+ Add to Wishlist' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));

        expect(
            screen.getByRole('heading', { name: 'Would you also accept other editions?' })
        ).toBeInTheDocument();

        await userEvent.click(screen.getByTestId('edition-preference-overlay'));

        expect(
            screen.queryByRole('heading', { name: 'Would you also accept other editions?' })
        ).not.toBeInTheDocument();

        await userEvent.click(screen.getByRole('button', { name: 'Edit edition preferences' }));

        expect(
            screen.getByRole('heading', { name: 'Would you also accept other editions?' })
        ).toBeInTheDocument();

        fireEvent.keyDown(window, { key: 'Escape' });

        expect(
            screen.queryByRole('heading', { name: 'Would you also accept other editions?' })
        ).not.toBeInTheDocument();
    });

    it('shows address prompt after first wishlist listing', async () => {
        wishlist.list.mockResolvedValue({
            data: { count: 0, results: [] },
        });
        wishlist.add.mockResolvedValue({
            data: {},
            headers: { 'x-address-prompt': 'add_now' },
        });

        renderWithProviders(<Wishlist />);

        await userEvent.click(await screen.findByRole('button', { name: '+ Add to Wishlist' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));
        await userEvent.click(screen.getByRole('button', { name: 'Add to Wishlist' }));

        expect(
            await screen.findByRole('heading', { name: 'Would you like to add your address now?' })
        ).toBeInTheDocument();
    });

    it('shows loading spinner while fetching', () => {
        wishlist.list.mockReturnValue(new Promise(() => {}));
        renderWithProviders(<Wishlist />);
        expect(document.querySelector('[class*="spinner"]') || document.querySelector('[class*="loading"]')).toBeTruthy();
    });

    it('shows error message when fetch fails', async () => {
        wishlist.list.mockRejectedValue(new Error('Network error'));
        renderWithProviders(<Wishlist />);
        expect(await screen.findByText(/network error/i)).toBeInTheDocument();
    });

    it('shows empty state with "Add your first wish" button', async () => {
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Wishlist />);
        expect(await screen.findByText(/your wishlist is empty/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /add your first wish/i })).toBeInTheDocument();
    });

    it('pauses and resumes a wishlist item', async () => {
        wishlist.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'wish-2',
                        min_condition: 'any',
                        is_active: true,
                        edition_preference: 'any',
                        created_at: '2026-04-20T12:00:00Z',
                        book: { id: 'book-2', title: 'Dune', authors: ['Frank Herbert'], isbn_13: '9780441013593' },
                    },
                ],
            },
        });
        wishlist.update.mockResolvedValue({ data: {} });
        renderWithProviders(<Wishlist />);
        await userEvent.click(await screen.findByRole('button', { name: 'Pause' }));
        await waitFor(() => expect(wishlist.update).toHaveBeenCalledWith('wish-2', expect.objectContaining({ is_active: false })));
    });

    it('removes a wishlist item', async () => {
        vi.spyOn(window, 'confirm').mockReturnValue(true);
        wishlist.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'wish-3',
                        min_condition: 'good',
                        is_active: true,
                        edition_preference: 'any',
                        created_at: '2026-04-20T12:00:00Z',
                        book: { id: 'book-3', title: 'Foundation', authors: ['Isaac Asimov'], isbn_13: '9780553293357' },
                    },
                ],
            },
        });
        wishlist.remove.mockResolvedValue({ data: {} });
        renderWithProviders(<Wishlist />);
        await userEvent.click(await screen.findByRole('button', { name: 'Remove' }));
        await waitFor(() => expect(wishlist.remove).toHaveBeenCalledWith('wish-3'));
        window.confirm.mockRestore();
    });

    it('changes sort-by select in empty state', async () => {
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Wishlist />);
        await screen.findByText(/your wishlist is empty/i);
        await userEvent.selectOptions(screen.getAllByRole('combobox')[0], 'title');
        await waitFor(() => {
            expect(wishlist.list).toHaveBeenCalledWith(expect.objectContaining({ sort_by: 'title' }));
        });
    });

    it('changes sort-order select in empty state', async () => {
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Wishlist />);
        await screen.findByText(/your wishlist is empty/i);
        await userEvent.selectOptions(screen.getAllByRole('combobox')[1], 'asc');
        await waitFor(() => {
            expect(wishlist.list).toHaveBeenCalledWith(expect.objectContaining({ sort_order: 'asc' }));
        });
    });

    it('changes sort-by select when items are shown', async () => {
        wishlist.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'wish-5',
                        min_condition: 'good',
                        is_active: true,
                        edition_preference: 'any',
                        created_at: '2026-04-20T12:00:00Z',
                        book: { id: 'book-5', title: 'Solaris', authors: ['Stanislaw Lem'], isbn_13: '9780156027601' },
                    },
                ],
            },
        });
        renderWithProviders(<Wishlist />);
        await screen.findByText('Solaris');
        await userEvent.selectOptions(screen.getAllByRole('combobox')[0], 'title');
        await waitFor(() => {
            expect(wishlist.list).toHaveBeenCalledWith(expect.objectContaining({ sort_by: 'title' }));
        });
    });

    it('changes sort-order select when items are shown', async () => {
        wishlist.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'wish-6',
                        min_condition: 'good',
                        is_active: true,
                        edition_preference: 'any',
                        created_at: '2026-04-20T12:00:00Z',
                        book: { id: 'book-6', title: 'Roadside Picnic', authors: ['Strugatsky'], isbn_13: '9781613743416' },
                    },
                ],
            },
        });
        renderWithProviders(<Wishlist />);
        await screen.findByText('Roadside Picnic');
        await userEvent.selectOptions(screen.getAllByRole('combobox')[1], 'asc');
        await waitFor(() => {
            expect(wishlist.list).toHaveBeenCalledWith(expect.objectContaining({ sort_order: 'asc' }));
        });
    });

    it('shows validation error when submitting add form with empty ISBN', async () => {
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Wishlist />);
        await userEvent.click(await screen.findByRole('button', { name: '+ Add to Wishlist' }));
        fireEvent.submit(document.querySelector('form'));
        expect(screen.getByText('Please enter an ISBN.')).toBeInTheDocument();
    });

    it('shows validation error when submitting add form without looking up book', async () => {
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Wishlist />);
        await userEvent.click(await screen.findByRole('button', { name: '+ Add to Wishlist' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        // Do NOT click Mock Lookup — foundBook is still null
        fireEvent.submit(document.querySelector('form'));
        expect(screen.getByText('Please look up the ISBN first.')).toBeInTheDocument();
    });

    it('shows error when wishlist add API fails', async () => {
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        wishlist.add.mockRejectedValueOnce({ response: { data: { detail: 'ISBN not found.' } } });
        renderWithProviders(<Wishlist />);
        await userEvent.click(await screen.findByRole('button', { name: '+ Add to Wishlist' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));
        await userEvent.click(screen.getByRole('button', { name: 'Add to Wishlist' }));
        await waitFor(() => expect(screen.getByText('ISBN not found.')).toBeInTheDocument());
    });

    it('shows generic error when wishlist add API fails without detail', async () => {
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        wishlist.add.mockRejectedValueOnce({ response: { data: {} } });
        renderWithProviders(<Wishlist />);
        await userEvent.click(await screen.findByRole('button', { name: '+ Add to Wishlist' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));
        await userEvent.click(screen.getByRole('button', { name: 'Add to Wishlist' }));
        await waitFor(() => expect(screen.getByText('Failed to add to wishlist.')).toBeInTheDocument());
    });

    it('submits wishlist item with non-any min_condition included in payload', async () => {
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        wishlist.add.mockResolvedValue({ data: {} });
        renderWithProviders(<Wishlist />);
        await userEvent.click(await screen.findByRole('button', { name: '+ Add to Wishlist' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));
        // foundBook is now set, min_condition select appears in the form
        await userEvent.selectOptions(screen.getByLabelText('Minimum acceptable condition'), 'good');
        await userEvent.click(screen.getByRole('button', { name: 'Add to Wishlist' }));
        expect(wishlist.add).toHaveBeenCalledWith(expect.objectContaining({ min_condition: 'good' }));
    });

    it('deselects a format preference when clicked a second time', async () => {
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        wishlist.add.mockResolvedValue({ data: {} });
        renderWithProviders(<Wishlist />);
        await userEvent.click(await screen.findByRole('button', { name: '+ Add to Wishlist' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));
        // popup appears; switch to custom so format buttons appear
        await userEvent.selectOptions(screen.getByLabelText('Edition matching'), 'custom');
        // Click Hardcover to select it, then again to deselect (covers filter branch)
        await userEvent.click(screen.getByRole('button', { name: 'Hardcover' }));
        await userEvent.click(screen.getByRole('button', { name: 'Hardcover' }));
        await userEvent.click(screen.getByRole('button', { name: 'Add to Wishlist' }));
        expect(wishlist.add).toHaveBeenCalledWith(expect.objectContaining({ format_preferences: [] }));
    });

    it('renders a paused wishlist item with "Paused" badge and "Resume" button', async () => {
        wishlist.list.mockResolvedValue({
            data: {
                count: 1,
                results: [{
                    id: 'wish-paused',
                    min_condition: 'good',
                    is_active: false,
                    edition_preference: 'any',
                    created_at: '2026-04-20T12:00:00Z',
                    book: { id: 'b-p', title: 'Paused Book', authors: ['Author'], isbn_13: '9780441013593' },
                }],
            },
        });
        renderWithProviders(<Wishlist />);
        expect(await screen.findByText('Paused Book')).toBeInTheDocument();
        // is_active: false → 'Paused' badge (badge-gray) and 'Resume' button (covers lines 513-524 false branch)
        expect(screen.getByText('Paused')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Resume' })).toBeInTheDocument();
    });

    it('returns defaults when user has id but no stored preferences in localStorage', async () => {
        localStorage.removeItem('wishlist-preferences:fresh-user');
        useAuth.mockReturnValue({ user: { id: 'fresh-user' } });
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Wishlist />);
        // userId defined, localStorage has no entry → raw = null → if (!raw) return DEFAULT (line 63)
        expect(await screen.findByText(/your wishlist is empty/i)).toBeInTheDocument();
    });

    it('loads stored wishlist preferences from localStorage when user is authenticated', async () => {
        localStorage.setItem(
            'wishlist-preferences:test-user-1',
            JSON.stringify({ min_condition: 'good', format_preferences: ['hardcover'] })
        );
        useAuth.mockReturnValue({ user: { id: 'test-user-1' } });
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Wishlist />);
        // loadStoredWishlistPreferences runs with valid JSON → covers lines 64-69
        expect(await screen.findByText(/your wishlist is empty/i)).toBeInTheDocument();
        localStorage.removeItem('wishlist-preferences:test-user-1');
    });

    it('uses empty array when stored format_preferences is not an array', async () => {
        localStorage.setItem(
            'wishlist-preferences:test-user-2',
            JSON.stringify({ min_condition: 'good' })  // no format_preferences key
        );
        useAuth.mockReturnValue({ user: { id: 'test-user-2' } });
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Wishlist />);
        // Array.isArray(undefined) = false → [] used (covers line 68 false branch)
        expect(await screen.findByText(/your wishlist is empty/i)).toBeInTheDocument();
        localStorage.removeItem('wishlist-preferences:test-user-2');
    });

    it('handles corrupt localStorage data gracefully and falls back to defaults', async () => {
        localStorage.setItem('wishlist-preferences:test-user-1', 'not-valid-json}}');
        useAuth.mockReturnValue({ user: { id: 'test-user-1' } });
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Wishlist />);
        // catch block fires → DEFAULT_WISHLIST_PREFERENCES used → no crash (covers lines 70-72)
        expect(await screen.findByText(/your wishlist is empty/i)).toBeInTheDocument();
        localStorage.removeItem('wishlist-preferences:test-user-1');
    });

    it('shows non_field_errors when wishlist add API fails with that field', async () => {
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        wishlist.add.mockRejectedValueOnce({
            response: { data: { non_field_errors: ['Already on your wishlist.'] } },
        });
        renderWithProviders(<Wishlist />);
        await userEvent.click(await screen.findByRole('button', { name: '+ Add to Wishlist' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));
        await userEvent.click(screen.getByRole('button', { name: 'Add to Wishlist' }));
        // no detail → non_field_errors.join(' ') used (covers line 137)
        await waitFor(() => expect(screen.getByText('Already on your wishlist.')).toBeInTheDocument());
    });

    it('shows "any_language" hint text when that edition preference is selected', async () => {
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Wishlist />);
        await userEvent.click(await screen.findByRole('button', { name: '+ Add to Wishlist' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));
        // Select any_language — covers line 321 (true branch for any_language hint text)
        await userEvent.selectOptions(screen.getByLabelText('Edition matching'), 'any_language');
        expect(screen.getByText('Any edition including translations.')).toBeInTheDocument();
    });

    it('shows "exact" hint text when that edition preference is selected', async () => {
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Wishlist />);
        await userEvent.click(await screen.findByRole('button', { name: '+ Add to Wishlist' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));
        // Select exact — covers line 319 (true branch for exact hint text)
        await userEvent.selectOptions(screen.getByLabelText('Edition matching'), 'exact');
        expect(screen.getByText('Only this exact ISBN will be matched.')).toBeInTheDocument();
    });

    it('renders a flat wishlist item (no nested book property) using item itself', async () => {
        wishlist.list.mockResolvedValue({
            data: {
                count: 1,
                results: [{
                    id: 'wish-flat',
                    min_condition: 'good',
                    is_active: true,
                    edition_preference: 'any',
                    created_at: '2026-04-20T12:00:00Z',
                    // No 'book' property — item.book ?? item → item (covers line 479)
                    title: 'Flat Wishlist Book',
                    isbn_13: '9780441013593',
                }],
            },
        });
        renderWithProviders(<Wishlist />);
        expect(await screen.findByText('Flat Wishlist Book')).toBeInTheDocument();
    });

    it('shows "Unknown Author" when book has no authors', async () => {
        wishlist.list.mockResolvedValue({
            data: {
                count: 1,
                results: [{
                    id: 'wish-noauthor',
                    min_condition: 'good',
                    is_active: true,
                    edition_preference: 'any',
                    created_at: '2026-04-20T12:00:00Z',
                    book: { id: 'b-na', title: 'No Author Book', authors: [], isbn_13: '9780441013593' },
                }],
            },
        });
        renderWithProviders(<Wishlist />);
        expect(await screen.findByText('No Author Book')).toBeInTheDocument();
        // getBookPrimaryAuthor returns null for empty authors array → ?? 'Unknown Author' (covers line 487)
        expect(screen.getByText('Unknown Author')).toBeInTheDocument();
    });

    it('shows "Any condition" badge when min_condition is "any"', async () => {
        wishlist.list.mockResolvedValue({
            data: {
                count: 1,
                results: [
                    {
                        id: 'wish-4',
                        min_condition: 'any',
                        is_active: true,
                        edition_preference: 'custom',
                        allow_translations: true,
                        created_at: '2026-04-20T12:00:00Z',
                        book: { id: 'book-4', title: 'Neuromancer', authors: ['Gibson'], isbn_13: '9780441569595' },
                    },
                ],
            },
        });
        renderWithProviders(<Wishlist />);
        expect(await screen.findByText(/any condition/i)).toBeInTheDocument();
        expect(screen.getByText(/includes translations/i)).toBeInTheDocument();
    });

    it('clicking "Add your first wish" shows the add form (covers empty-state onClick at line 438)', async () => {
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Wishlist />);
        await userEvent.click(await screen.findByRole('button', { name: /add your first wish/i }));
        // Add form should now be visible
        expect(screen.getByLabelText('ISBN')).toBeInTheDocument();
    });

    it('covers edition prompt: allowTranslations onChange and Done button onClick (lines 342, 373)', async () => {
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        renderWithProviders(<Wishlist />);
        await userEvent.click(await screen.findByRole('button', { name: '+ Add to Wishlist' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        // Mock Lookup triggers handleBookFound → showEditionPrompt becomes true
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));

        // The allowTranslations checkbox is only shown when editionPreference === 'custom'
        // Change the edition preference select to 'custom' to reveal the checkbox section
        await userEvent.selectOptions(screen.getByLabelText('Edition matching'), 'custom');

        // Toggle the "Include translations" checkbox (covers onChange at line 342)
        const transCheckbox = screen.getAllByRole('checkbox')[0]; // first checkbox in custom section
        await userEvent.click(transCheckbox);

        // Click Done (covers onClick={() => setShowEditionPrompt(false)} at line 373)
        await userEvent.click(screen.getByRole('button', { name: 'Done' }));
        // Dialog should be gone
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('covers AddressPromptModal onClose callback (line 542) by clicking "Not now"', async () => {
        wishlist.list.mockResolvedValue({ data: { count: 0, results: [] } });
        wishlist.add.mockResolvedValue({
            data: {},
            headers: { 'x-address-prompt': 'add_now' },
        });
        renderWithProviders(<Wishlist />);
        await userEvent.click(await screen.findByRole('button', { name: '+ Add to Wishlist' }));
        await userEvent.type(screen.getByLabelText('ISBN'), '9780393081084');
        await userEvent.click(screen.getByRole('button', { name: 'Mock Lookup' }));
        await userEvent.click(screen.getByRole('button', { name: 'Add to Wishlist' }));
        // Address prompt appears
        await screen.findByRole('heading', { name: 'Would you like to add your address now?' });
        // Dismiss it — covers onClose={() => setShowAddressPrompt(false)} at line 542
        await userEvent.click(screen.getByRole('button', { name: /not now/i }));
        expect(screen.queryByRole('heading', { name: /would you like to add your address/i })).not.toBeInTheDocument();
    });
});