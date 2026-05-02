import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeAll } from 'vitest';
import BookPopover from './BookPopover.jsx';

// Mock ResizeObserver which is missing in JSDOM
beforeAll(() => {
  global.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

const book = {
  id: '1',
  title: 'Test Book',
  authors: ['Test Author'],
  isbn_13: '9780123456789',
  physical_format: 'Paperback',
  page_count: 200,
  publish_year: 2020,
  subjects: ['Fiction', 'Adventure'],
  description: 'This is a test book description.',
  publisher: 'Test Publisher',
};

describe('BookPopover', () => {
  it('renders nothing when book is missing', () => {
    const { container } = render(<BookPopover book={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders trigger button', () => {
    render(<BookPopover book={book} />);
    expect(screen.getByRole('button', { name: /view book details/i })).toBeInTheDocument();
  });

  it('opens popover on click and shows book details', async () => {
    render(<BookPopover book={book} />);
    const trigger = screen.getByRole('button', { name: /view book details/i });
    
    await userEvent.click(trigger);

    // Metadata should appear in the document
    expect(await screen.findByText('Test Book')).toBeInTheDocument();
    expect(screen.getByText('by Test Author')).toBeInTheDocument();
    expect(screen.getByText('Paperback')).toBeInTheDocument();
    expect(screen.getByText('200 pages')).toBeInTheDocument();
    expect(screen.getByText('Published 2020')).toBeInTheDocument();
    expect(screen.getByText('Fiction')).toBeInTheDocument();
    expect(screen.getByText('Adventure')).toBeInTheDocument();
    expect(screen.getByText('This is a test book description.')).toBeInTheDocument();
    expect(screen.getByText('ISBN: 9780123456789')).toBeInTheDocument();
    expect(screen.getByText('Publisher: Test Publisher')).toBeInTheDocument();
  });

  it('shows fallback text when description is missing', async () => {
    const bookNoDesc = { ...book, description: null };
    render(<BookPopover book={bookNoDesc} />);
    
    await userEvent.click(screen.getByRole('button', { name: /view book details/i }));
    
    expect(await screen.findByText(/no synopsis available/i)).toBeInTheDocument();
  });

  it('closes when close button is clicked', async () => {
    render(<BookPopover book={book} />);
    await userEvent.click(screen.getByRole('button', { name: /view book details/i }));
    
    const closeBtn = await screen.findByRole('button', { name: /close/i });
    await userEvent.click(closeBtn);
    
    await waitFor(() => {
      expect(screen.queryByText('Test Book')).not.toBeInTheDocument();
    });
  });
});
