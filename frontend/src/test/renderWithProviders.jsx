/**
 * renderWithProviders — wraps a component under test with all required providers:
 *   - MemoryRouter (with optional initialEntries)
 *   - QueryClientProvider (fresh client per test, no retries)
 *
 * Usage:
 *   const { getByText } = renderWithProviders(<MyComponent />, { route: '/some/path' });
 */
import React from 'react';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

export function renderWithProviders(ui, { route = '/', queryClient, ...renderOptions } = {}) {
  const client = queryClient ?? createTestQueryClient();

  function Wrapper({ children }) {
    return (
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }

  return { ...render(ui, { wrapper: Wrapper, ...renderOptions }), queryClient: client };
}
