import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import MyBooks from './MyBooks.jsx';
import { myBooks as myBooksApi } from '../services/api.js';

// Mock ResizeObserver
beforeAll(() => {
  global.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

vi.mock('../services/api.js', () => ({
  myBooks: {
    list: vi.fn(),
    add: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
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

const mockBooksResponse = {
  data: {
    count: 1,
    results: [
      {
        id: 'u1',
        book: {
          id: 'b1',
          title: 'Test Book',
          authors: ['Author One'],
          isbn_13: '9780141036144',
          physical_format: 'Paperback',
        },
        condition: 'good',
        status: 'available',
        created_at: '2026-05-01T12:00:00Z',
      },
    ],
  }
};

describe('MyBooks Page', () => {
  beforeEach(() => {
    queryClient.clear();
    vi.clearAllMocks();
    vi.stubGlobal('confirm', vi.fn().mockReturnValue(true));
  });

  it('renders loading status initially', () => {
    myBooksApi.list.mockReturnValue(new Promise(() => {}));
    render(<MyBooks />, { wrapper });
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders empty state when no books found', async () => {
    myBooksApi.list.mockResolvedValue({ data: { count: 0, results: [] } });
    render(<MyBooks />, { wrapper });
    expect(await screen.findByText(/no books yet/i)).toBeInTheDocument();
  });

  it('renders book list correctly', async () => {
    myBooksApi.list.mockResolvedValue(mockBooksResponse);
    render(<MyBooks />, { wrapper });

    expect(await screen.findByText('Test Book')).toBeInTheDocument();
    expect(screen.getByText('Author One')).toBeInTheDocument();
    expect(screen.getByText('9780141036144')).toBeInTheDocument();
    expect(screen.getByText(/Available/)).toBeInTheDocument();
  });

  it('allows showing and canceling add form', async () => {
    myBooksApi.list.mockResolvedValue({ data: { count: 0, results: [] } });
    render(<MyBooks />, { wrapper });
    
    const addBtn = await screen.findByRole('button', { name: /\+ Add Book/i });
    await userEvent.click(addBtn);
    
    expect(screen.getByText(/Add a Book/i)).toBeInTheDocument();
    
    const cancelBtn = screen.getByRole('button', { name: /Cancel/i });
    await userEvent.click(cancelBtn);
    
    expect(screen.queryByText(/Add a Book/i)).not.toBeInTheDocument();
  });

  it('allows removing a book', async () => {
    myBooksApi.list.mockResolvedValue(mockBooksResponse);
    myBooksApi.remove.mockResolvedValue({ data: {} });
    
    render(<MyBooks />, { wrapper });
    const removeBtn = await screen.findByRole('button', { name: /Remove/i });
    
    await userEvent.click(removeBtn);
    
    expect(window.confirm).toHaveBeenCalled();
    expect(myBooksApi.remove).toHaveBeenCalledWith('u1');
  });

  it('allows editing book condition', async () => {
    myBooksApi.list.mockResolvedValue(mockBooksResponse);
    myBooksApi.update.mockResolvedValue({ data: { ...mockBooksResponse.data.results[0], condition: 'like_new' } });
    
    render(<MyBooks />, { wrapper });
    const editBtn = await screen.findByRole('button', { name: /Edit/i });
    
    await userEvent.click(editBtn);
    
    // Select the condition combobox inside the edit form
    const bookItem = screen.getByText('Test Book').closest('.card');
    const select = within(bookItem).getByRole('combobox');
    await userEvent.selectOptions(select, 'like_new');
    
    const saveBtn = within(bookItem).getByRole('button', { name: /Save/i });
    await userEvent.click(saveBtn);
    
    expect(myBooksApi.update).toHaveBeenCalledWith('u1', { condition: 'like_new' });
    await waitFor(() => {
        expect(within(bookItem).queryByRole('button', { name: /Save/i })).not.toBeInTheDocument();
    });
  });
});
