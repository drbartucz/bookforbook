import React from 'react';
import { screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import Layout from './Layout.jsx';

function renderLayout(children) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    return render(
        <QueryClientProvider client={client}>
            <MemoryRouter initialEntries={['/']}>
                <Routes>
                    <Route element={<Layout />}>
                        <Route index element={<>{children}</>} />
                    </Route>
                </Routes>
            </MemoryRouter>
        </QueryClientProvider>
    );
}

describe('Layout', () => {
    it('renders the outlet content', () => {
        renderLayout(<p>Outlet content</p>);
        expect(screen.getByText('Outlet content')).toBeInTheDocument();
    });

    it('renders the footer copyright notice', () => {
        renderLayout(null);
        expect(screen.getByText(/Trade books 1-for-1/i)).toBeInTheDocument();
    });

    it('renders the navbar', () => {
        renderLayout(null);
        // Navbar renders a nav element
        expect(document.querySelector('nav')).toBeInTheDocument();
    });
});
