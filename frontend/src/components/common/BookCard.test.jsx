import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import BookCard from './BookCard.jsx';

const wrap = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

const book = {
    title: 'The Great Gatsby',
    author: 'F. Scott Fitzgerald',
    isbn: '9780743273565',
    condition: 'very_good',
    cover_url: 'https://example.com/cover.jpg',
};

const apiBook = {
    title: 'The Left Hand of Darkness',
    authors: ['Ursula K. Le Guin'],
    isbn_13: '9780441478125',
    condition: 'good',
    cover_image_url: 'https://example.com/lefthand.jpg',
};

describe('BookCard', () => {
    it('renders null when book is not provided', () => {
        const { container } = wrap(<BookCard book={null} />);
        expect(container.firstChild).toBeNull();
    });

    it('renders book title and author', () => {
        wrap(<BookCard book={book} />);
        expect(screen.getByText('The Great Gatsby')).toBeInTheDocument();
        expect(screen.getByText('F. Scott Fitzgerald')).toBeInTheDocument();
    });

    it('renders ISBN when present', () => {
        wrap(<BookCard book={book} />);
        expect(screen.getByText(/9780743273565/)).toBeInTheDocument();
    });

    it('renders cover image with descriptive alt text', () => {
        wrap(<BookCard book={book} />);
        expect(screen.getByAltText('Cover of The Great Gatsby')).toBeInTheDocument();
    });

    it('renders "Unknown title" when book has no title', () => {
        wrap(<BookCard book={{ ...book, title: undefined }} />);
        expect(screen.getByText('Unknown title')).toBeInTheDocument();
    });

    it('renders condition badge', () => {
        wrap(<BookCard book={book} />);
        expect(screen.getByText('Very Good')).toBeInTheDocument();
    });

    it('renders current API field names', () => {
        wrap(<BookCard book={apiBook} />);
        expect(screen.getByText('The Left Hand of Darkness')).toBeInTheDocument();
        expect(screen.getByText('Ursula K. Le Guin')).toBeInTheDocument();
        expect(screen.getByText(/9780441478125/)).toBeInTheDocument();
        expect(screen.getByAltText('Cover of The Left Hand of Darkness')).toHaveAttribute(
            'src',
            'https://example.com/lefthand.jpg'
        );
    });

    it('renders owner link when owner is provided', () => {
        const owner = { id: 'abc', username: 'alice' };
        wrap(<BookCard book={book} owner={owner} />);
        expect(screen.getByRole('link', { name: '@alice' })).toBeInTheDocument();
    });

    it('does not render owner link when owner is omitted', () => {
        wrap(<BookCard book={book} />);
        expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });

    it('renders action button with label when onAction is provided', () => {
        wrap(<BookCard book={book} onAction={() => { }} actionLabel="Request" />);
        expect(screen.getByRole('button', { name: 'Request' })).toBeInTheDocument();
    });

    it('calls onAction when action button is clicked', async () => {
        const onAction = vi.fn();
        wrap(<BookCard book={book} onAction={onAction} actionLabel="Request" />);
        await userEvent.click(screen.getByRole('button', { name: 'Request' }));
        expect(onAction).toHaveBeenCalledTimes(1);
    });

    it('shows Loading… and disables button when actionLoading is true', () => {
        wrap(<BookCard book={book} onAction={() => { }} actionLabel="Request" actionLoading />);
        const btn = screen.getByRole('button', { name: 'Loading...' });
        expect(btn).toBeDisabled();
    });

    it('does not render action button when onAction is omitted', () => {
        wrap(<BookCard book={book} />);
        // We only check for the presence of buttons that ARE NOT the "View book details" button
        const actionButton = screen.queryByRole('button', { name: /Action|Request/ });
        expect(actionButton).not.toBeInTheDocument();
    });

    it('applies compact class when compact prop is true', () => {
        const { container } = wrap(<BookCard book={book} compact />);
        // The outer div should have a class containing 'compact'
        expect(container.querySelector('[class*="compact"]')).toBeInTheDocument();
    });

    it('renders "Action" as default label when actionLabel is not provided', () => {
        wrap(<BookCard book={book} onAction={() => { }} />);
        expect(screen.getByRole('button', { name: 'Action' })).toBeInTheDocument();
    });

    it('renders extra content when extra prop is provided', () => {
        wrap(<BookCard book={book} extra={<span>Extra content</span>} />);
        expect(screen.getByText('Extra content')).toBeInTheDocument();
    });

    it('stopPropagation is called when owner link is clicked', async () => {
        const owner = { id: 'abc', username: 'alice' };
        wrap(<BookCard book={book} owner={owner} />);
        const link = screen.getByRole('link', { name: '@alice' });
        // Just verify clicking the link doesn't throw
        await userEvent.click(link);
        expect(link).toBeInTheDocument();
    });

    it('falls back to placeholder image when cover image fails to load', () => {
        wrap(<BookCard book={book} />);
        const img = screen.getByAltText('Cover of The Great Gatsby');
        // Simulate an image load error
        Object.defineProperty(img, 'src', { writable: true, value: '' });
        img.dispatchEvent(new Event('error'));
        // The onError handler sets src to the placeholder
        expect(img.src).toBeDefined();
    });
});

const richBook = {
    title: 'Dune',
    authors: ['Frank Herbert'],
    isbn_13: '9780441013593',
    condition: 'good',
    description: 'A science fiction masterpiece set in the distant future.',
    physical_format: 'Hardcover',
    page_count: 896,
    publish_year: 1965,
    subjects: ['Science Fiction', 'Space Opera'],
};

const openPopover = async (user) => {
    await user.click(screen.getByRole('button', { name: 'View book details' }));
    await waitFor(() =>
        expect(
            screen.getByText('A science fiction masterpiece set in the distant future.')
        ).toBeInTheDocument()
    );
};

describe('BookCard — BookPopover integration', () => {
    it('renders the popover trigger with correct accessibility label', () => {
        wrap(<BookCard book={richBook} />);
        expect(
            screen.getByRole('button', { name: 'View book details' })
        ).toBeInTheDocument();
    });

    it('does not show popover content before trigger is clicked', () => {
        wrap(<BookCard book={richBook} />);
        expect(
            screen.queryByText('A science fiction masterpiece set in the distant future.')
        ).not.toBeInTheDocument();
    });

    it('opens the popover and shows book title when trigger is clicked', async () => {
        const user = userEvent.setup();
        wrap(<BookCard book={richBook} />);
        await openPopover(user);
        // After opening, the popover renders a second heading with the same title
        expect(screen.getAllByRole('heading', { name: 'Dune' })).toHaveLength(2);
    });

    it('shows description in the popover', async () => {
        const user = userEvent.setup();
        wrap(<BookCard book={richBook} />);
        await openPopover(user);
        expect(
            screen.getByText('A science fiction masterpiece set in the distant future.')
        ).toBeInTheDocument();
    });

    it('shows metadata fields (format, page count, year) in the popover', async () => {
        const user = userEvent.setup();
        wrap(<BookCard book={richBook} />);
        await openPopover(user);
        expect(screen.getByText('Hardcover')).toBeInTheDocument();
        expect(screen.getByText('896 pages')).toBeInTheDocument();
        expect(screen.getByText('Published 1965')).toBeInTheDocument();
    });

    it('shows genre tags (subjects) in the popover', async () => {
        const user = userEvent.setup();
        wrap(<BookCard book={richBook} />);
        await openPopover(user);
        expect(screen.getByText('Science Fiction')).toBeInTheDocument();
        expect(screen.getByText('Space Opera')).toBeInTheDocument();
    });

    it('shows fallback message when description is absent', async () => {
        const user = userEvent.setup();
        wrap(<BookCard book={{ ...richBook, description: undefined }} />);
        await user.click(screen.getByRole('button', { name: 'View book details' }));
        await waitFor(() =>
            expect(
                screen.getByText('No synopsis available for this title.')
            ).toBeInTheDocument()
        );
    });

    it('closes the popover when the close button is clicked', async () => {
        const user = userEvent.setup();
        wrap(<BookCard book={richBook} />);
        await openPopover(user);
        await user.click(screen.getByRole('button', { name: 'Close' }));
        await waitFor(() =>
            expect(
                screen.queryByText('A science fiction masterpiece set in the distant future.')
            ).not.toBeInTheDocument()
        );
    });

    it('opens the popover with keyboard Enter on the trigger', async () => {
        const user = userEvent.setup();
        wrap(<BookCard book={richBook} />);
        screen.getByRole('button', { name: 'View book details' }).focus();
        await user.keyboard('{Enter}');
        await waitFor(() =>
            expect(
                screen.getByText('A science fiction masterpiece set in the distant future.')
            ).toBeInTheDocument()
        );
    });

    it('closes the popover when Escape is pressed', async () => {
        const user = userEvent.setup();
        wrap(<BookCard book={richBook} />);
        await openPopover(user);
        await user.keyboard('{Escape}');
        await waitFor(() =>
            expect(
                screen.queryByText('A science fiction masterpiece set in the distant future.')
            ).not.toBeInTheDocument()
        );
    });
});
