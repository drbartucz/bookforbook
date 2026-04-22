import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Matches from './Matches.jsx';

vi.mock('../services/api.js', () => ({
  matches: {
    list: vi.fn(),
    accept: vi.fn(),
    decline: vi.fn(),
  },
}));

import { matches } from '../services/api.js';

describe('Matches page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders match books from the current API shape and accepts a match', async () => {
    matches.list.mockResolvedValue({
      data: {
        count: 1,
        results: [
          {
            id: 'match-1',
            status: 'pending',
            partner: { id: 'user-2', username: 'alice', avg_recent_rating: 4.7 },
            your_book: {
              condition: 'good',
              book: {
                id: 'book-1',
                title: 'Kindred',
                authors: ['Octavia E. Butler'],
                cover_image_url: 'https://example.com/kindred.jpg',
              },
            },
            their_book: {
              condition: 'very_good',
              book: {
                id: 'book-2',
                title: 'The Dispossessed',
                authors: ['Ursula K. Le Guin'],
                cover_image_url: 'https://example.com/dispossessed.jpg',
              },
            },
          },
        ],
      },
    });
    matches.accept.mockResolvedValue({ data: {} });

    renderWithProviders(<Matches />);

    expect(await screen.findByText('Kindred')).toBeInTheDocument();
    expect(screen.getByText('Octavia E. Butler')).toBeInTheDocument();
    expect(screen.getByText('The Dispossessed')).toBeInTheDocument();
    expect(screen.getByText('Ursula K. Le Guin')).toBeInTheDocument();
    expect(screen.getByAltText('Kindred')).toHaveAttribute('src', 'https://example.com/kindred.jpg');
    expect(screen.getByAltText('The Dispossessed')).toHaveAttribute('src', 'https://example.com/dispossessed.jpg');

    await userEvent.click(screen.getByRole('button', { name: 'Accept Match' }));

    await waitFor(() => {
      expect(matches.accept).toHaveBeenCalledWith('match-1');
    });
  });
});