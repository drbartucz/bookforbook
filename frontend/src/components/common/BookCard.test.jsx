import React from 'react';
import { render, screen } from '@testing-library/react';
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
        expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });
});
