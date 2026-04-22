import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Home from './Home.jsx';

vi.mock('../services/api.js', () => ({
  browse: {
    available: vi.fn(),
  },
  wishlist: {
    add: vi.fn(),
  },
}));

vi.mock('../hooks/useAuth.js', () => ({
  default: vi.fn(),
}));

vi.mock('../hooks/useDebounce.js', () => ({
  default: vi.fn((value) => value),
}));

import { browse, wishlist } from '../services/api.js';
import useAuth from '../hooks/useAuth.js';

describe('Home page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders books from the current API shape and adds wishlist items using isbn_13', async () => {
    useAuth.mockReturnValue({
      isAuthenticated: true,
    });

    browse.available.mockResolvedValue({
      data: {
        count: 1,
        results: [
          {
            id: 'listing-1',
            owner: { id: 'user-1', username: 'alice' },
            book: {
              id: 'book-1',
              title: 'The Left Hand of Darkness',
              authors: ['Ursula K. Le Guin'],
              isbn_13: '9780441478125',
              cover_image_url: 'https://example.com/lefthand.jpg',
              condition: 'good',
            },
          },
        ],
      },
    });
    wishlist.add.mockResolvedValue({ data: {} });

    renderWithProviders(<Home />);

    expect(await screen.findByText('The Left Hand of Darkness')).toBeInTheDocument();
    expect(screen.getByText('Ursula K. Le Guin')).toBeInTheDocument();
    expect(screen.getByText(/9780441478125/)).toBeInTheDocument();
    expect(screen.getByAltText('Cover of The Left Hand of Darkness')).toHaveAttribute(
      'src',
      'https://example.com/lefthand.jpg'
    );

    await userEvent.click(screen.getByRole('button', { name: 'Want this' }));

    await waitFor(() => {
      expect(wishlist.add).toHaveBeenCalledWith({ isbn: '9780441478125' });
    });
  });
});