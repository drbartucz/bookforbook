import React from 'react';
import { screen } from '@testing-library/react';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import PublicProfile from './PublicProfile.jsx';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: vi.fn(() => ({ id: 'institution-1' })),
  };
});

vi.mock('../services/api.js', () => ({
  users: {
    getPublicProfile: vi.fn(),
    getUserRatings: vi.fn(),
  },
  institutions: {
    getWantedList: vi.fn(),
  },
}));

import { institutions, users } from '../services/api.js';

describe('PublicProfile page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders institution wanted books from the current API shape', async () => {
    users.getPublicProfile.mockResolvedValue({
      data: {
        id: 'institution-1',
        username: 'central-library',
        account_type: 'institution',
        is_verified: true,
        total_trades: 12,
      },
    });
    users.getUserRatings.mockResolvedValue({ data: [] });
    institutions.getWantedList.mockResolvedValue({
      data: [
        {
          id: 'wanted-1',
          min_condition: 'good',
          quantity_needed: 2,
          book: {
            id: 'book-1',
            title: 'Beloved',
            authors: ['Toni Morrison'],
            cover_image_url: 'https://example.com/beloved.jpg',
          },
        },
      ],
    });

    renderWithProviders(<PublicProfile />);

    expect(await screen.findByText('Beloved')).toBeInTheDocument();
    expect(screen.getByText('Toni Morrison')).toBeInTheDocument();
    expect(screen.getByAltText('Beloved')).toHaveAttribute('src', 'https://example.com/beloved.jpg');
    expect(screen.getByText(/Need: 2/)).toBeInTheDocument();
  });
});