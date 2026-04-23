import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { vi } from 'vitest';

// Mock useAuth so we can control authentication state
vi.mock('./hooks/useAuth.js', () => ({
    default: vi.fn(),
}));

// Mock all page components to avoid complex rendering side-effects
vi.mock('./pages/Home.jsx', () => ({ default: () => <div data-testid="home-page" /> }));
vi.mock('./pages/Login.jsx', () => ({ default: () => <div data-testid="login-page" /> }));
vi.mock('./pages/Register.jsx', () => ({ default: () => <div data-testid="register-page" /> }));
vi.mock('./pages/VerifyEmail.jsx', () => ({ default: () => <div data-testid="verify-email-page" /> }));
vi.mock('./pages/Dashboard.jsx', () => ({ default: () => <div data-testid="dashboard-page" /> }));
vi.mock('./pages/AccountSettings.jsx', () => ({ default: () => <div data-testid="account-settings-page" /> }));
vi.mock('./pages/MyBooks.jsx', () => ({ default: () => <div data-testid="my-books-page" /> }));
vi.mock('./pages/Wishlist.jsx', () => ({ default: () => <div data-testid="wishlist-page" /> }));
vi.mock('./pages/Matches.jsx', () => ({ default: () => <div data-testid="matches-page" /> }));
vi.mock('./pages/Proposals.jsx', () => ({ default: () => <div data-testid="proposals-page" /> }));
vi.mock('./pages/Trades.jsx', () => ({ default: () => <div data-testid="trades-page" /> }));
vi.mock('./pages/TradeDetail.jsx', () => ({ default: () => <div data-testid="trade-detail-page" /> }));
vi.mock('./pages/Donations.jsx', () => ({ default: () => <div data-testid="donations-page" /> }));
vi.mock('./pages/PublicProfile.jsx', () => ({ default: () => <div data-testid="public-profile-page" /> }));
vi.mock('./pages/Institutions.jsx', () => ({ default: () => <div data-testid="institutions-page" /> }));
vi.mock('./components/layout/Layout.jsx', () => ({
    default: () => {
        const { Outlet } = require('react-router-dom');
        return <Outlet />;
    },
}));

import useAuth from './hooks/useAuth.js';
import App from './App.jsx';

function renderApp(initialRoute, authState = {}) {
    useAuth.mockReturnValue({
        isAuthenticated: false,
        isIndividual: false,
        isInstitution: false,
        login: vi.fn(),
        logout: vi.fn(),
        ...authState,
    });

    const client = new QueryClient({
        defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });

    return render(
        <QueryClientProvider client={client}>
            <MemoryRouter initialEntries={[initialRoute]}>
                <App />
            </MemoryRouter>
        </QueryClientProvider>
    );
}

describe('ProtectedRoute', () => {
    it('redirects unauthenticated user from /dashboard to /login', () => {
        renderApp('/dashboard', { isAuthenticated: false });
        expect(screen.getByTestId('login-page')).toBeInTheDocument();
        expect(screen.queryByTestId('dashboard-page')).not.toBeInTheDocument();
    });

    it('renders protected page for authenticated user', () => {
        renderApp('/dashboard', { isAuthenticated: true });
        expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
        expect(screen.queryByTestId('login-page')).not.toBeInTheDocument();
    });

    it('redirects unauthenticated user from /my-books to /login', () => {
        renderApp('/my-books', { isAuthenticated: false });
        expect(screen.getByTestId('login-page')).toBeInTheDocument();
    });

    it('renders account settings for authenticated user', () => {
        renderApp('/account', { isAuthenticated: true });
        expect(screen.getByTestId('account-settings-page')).toBeInTheDocument();
    });

    it('redirects unauthenticated user from /account to /login', () => {
        renderApp('/account', { isAuthenticated: false });
        expect(screen.getByTestId('login-page')).toBeInTheDocument();
    });
});

describe('GuestRoute', () => {
    it('redirects authenticated user from /login to /dashboard', () => {
        renderApp('/login', { isAuthenticated: true });
        expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
        expect(screen.queryByTestId('login-page')).not.toBeInTheDocument();
    });

    it('renders login page for unauthenticated user', () => {
        renderApp('/login', { isAuthenticated: false });
        expect(screen.getByTestId('login-page')).toBeInTheDocument();
    });

    it('redirects authenticated user from /register to /dashboard', () => {
        renderApp('/register', { isAuthenticated: true });
        expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
        expect(screen.queryByTestId('register-page')).not.toBeInTheDocument();
    });
});
