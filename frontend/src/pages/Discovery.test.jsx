import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest';
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import Discovery from './Discovery.jsx';
import { matches as matchesApi, wishlist as wishlistApi } from '../services/api.js';

// Mock ResizeObserver
beforeAll(() => {
  global.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

vi.mock('../services/api.js', () => ({
  matches: {
    reverseDiscovery: vi.fn(),
  },
  wishlist: {
    add: vi.fn(),
  },
}));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

const wrapper = ({ children }) => (
  <QueryClientProvider client={queryClient}>
    <MemoryRouter>{children}</MemoryRouter>
  </QueryClientProvider>
);

const mockPartners = [
  {
    user: { id: '1', username: 'partner1', avg_recent_rating: 4.5 },
    they_want: [
      { id: 'u1', book: { title: 'My Book 1' } }
    ],
    they_offer: [
      { id: 'u2', book: { id: 'b1', title: 'Offer Book 1', isbn_13: '1234567890123' } }
    ],
  }
];

describe('Discovery Page', () => {
  beforeEach(() => {
    queryClient.clear();
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    matchesApi.reverseDiscovery.mockReturnValue(new Promise(() => {}));
    render(<Discovery />, { wrapper });
    expect(screen.getByText(/finding potential trade partners/i)).toBeInTheDocument();
  });

  it('renders empty state when no partners found', async () => {
    matchesApi.reverseDiscovery.mockResolvedValue({ data: [] });
    render(<Discovery />, { wrapper });
    expect(await screen.findByText(/no potential partners found yet/i)).toBeInTheDocument();
  });

  it('renders error state on API failure', async () => {
    matchesApi.reverseDiscovery.mockRejectedValue(new Error('API error'));
    render(<Discovery />, { wrapper });
    expect(await screen.findByText(/error/i)).toBeInTheDocument();
  });

  it('renders partners and their books correctly', async () => {
    matchesApi.reverseDiscovery.mockResolvedValue({ data: mockPartners });
    render(<Discovery />, { wrapper });

    expect(await screen.findByText('@partner1')).toBeInTheDocument();
    expect(screen.getByText(/4\.5\s*★/)).toBeInTheDocument();
    expect(screen.getByText('My Book 1')).toBeInTheDocument();
    expect(screen.getByText('Offer Book 1')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /i want this/i })).toBeInTheDocument();
  });

  it('allows adding a book to wishlist', async () => {
    matchesApi.reverseDiscovery.mockResolvedValue({ data: mockPartners });
    wishlistApi.add.mockResolvedValue({ data: {} });
    
    render(<Discovery />, { wrapper });
    const addBtn = await screen.findByRole('button', { name: /i want this/i });
    
    await userEvent.click(addBtn);
    
    expect(wishlistApi.add).toHaveBeenCalledWith({ isbn: '1234567890123' });
    
    // Check if the button changes its label
    await waitFor(() => {
        const btn = screen.queryByRole('button', { name: /Added!/i });
        expect(btn).toBeInTheDocument();
    });
  });
});
