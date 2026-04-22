import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Donations from './Donations.jsx';

vi.mock('../services/api.js', () => ({
  donations: {
    list: vi.fn(),
    accept: vi.fn(),
    decline: vi.fn(),
  },
}));

import { donations } from '../services/api.js';

describe('Donations page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders donation books from the current API shape and accepts a donation', async () => {
    donations.list.mockResolvedValue({
      data: {
        count: 1,
        results: [
          {
            id: 'donation-1',
            status: 'pending',
            created_at: '2026-04-20T12:00:00Z',
            is_recipient: true,
            donor: { id: 'user-1', username: 'bart0605' },
            recipient: { id: 'inst-1', username: 'central-library' },
            book: {
              condition: 'good',
              book: {
                id: 'book-1',
                title: 'The Bluest Eye',
                authors: ['Toni Morrison'],
                cover_image_url: 'https://example.com/bluesteye.jpg',
              },
            },
          },
        ],
      },
    });
    donations.accept.mockResolvedValue({ data: {} });

    renderWithProviders(<Donations />);

    expect(await screen.findByText('The Bluest Eye')).toBeInTheDocument();
    expect(screen.getByText('Toni Morrison')).toBeInTheDocument();
    expect(screen.getByAltText('The Bluest Eye')).toHaveAttribute('src', 'https://example.com/bluesteye.jpg');
    expect(screen.getByText('@central-library')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Accept Donation' }));

    await waitFor(() => {
      expect(donations.accept).toHaveBeenCalledWith('donation-1');
    });
  });
});