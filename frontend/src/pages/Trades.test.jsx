import React from 'react';
import { screen } from '@testing-library/react';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Trades from './Trades.jsx';

vi.mock('../services/api.js', () => ({
  trades: {
    list: vi.fn(),
  },
}));

import { trades } from '../services/api.js';

describe('Trades page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders trade books from the current API shape', async () => {
    trades.list.mockResolvedValue({
      data: {
        count: 1,
        results: [
          {
            id: 'trade-1',
            status: 'confirmed',
            created_at: '2026-04-20T12:00:00Z',
            partner: { id: 'user-2', username: 'bob' },
            initiator_book: {
              book: {
                id: 'book-1',
                title: 'Parable of the Sower',
                authors: ['Octavia E. Butler'],
                cover_image_url: 'https://example.com/sower.jpg',
              },
            },
            responder_book: {
              book: {
                id: 'book-2',
                title: 'A Wizard of Earthsea',
                authors: ['Ursula K. Le Guin'],
                cover_image_url: 'https://example.com/earthsea.jpg',
              },
            },
          },
        ],
      },
    });

    renderWithProviders(<Trades />);

    expect(await screen.findByText('Parable of the Sower')).toBeInTheDocument();
    expect(screen.getByText('Octavia E. Butler')).toBeInTheDocument();
    expect(screen.getByText('A Wizard of Earthsea')).toBeInTheDocument();
    expect(screen.getByText('Ursula K. Le Guin')).toBeInTheDocument();
    expect(screen.getByAltText('Parable of the Sower')).toHaveAttribute(
      'src',
      'https://example.com/sower.jpg'
    );
    expect(screen.getByAltText('A Wizard of Earthsea')).toHaveAttribute(
      'src',
      'https://example.com/earthsea.jpg'
    );
    expect(screen.getByText('@bob')).toBeInTheDocument();
  });
});