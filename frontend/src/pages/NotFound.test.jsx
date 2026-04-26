import React from 'react';
import { screen } from '@testing-library/react';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import NotFound from './NotFound.jsx';

describe('NotFound page', () => {
    it('renders the 404 badge', () => {
        renderWithProviders(<NotFound />);
        expect(screen.getByText('404')).toBeInTheDocument();
    });

    it('renders the page-not-found heading', () => {
        renderWithProviders(<NotFound />);
        expect(screen.getByRole('heading', { name: /page not found/i })).toBeInTheDocument();
    });

    it('renders a Go home link', () => {
        renderWithProviders(<NotFound />);
        expect(screen.getByRole('link', { name: /go home/i })).toHaveAttribute('href', '/');
    });

    it('renders a Go to dashboard link', () => {
        renderWithProviders(<NotFound />);
        expect(screen.getByRole('link', { name: /go to dashboard/i })).toHaveAttribute('href', '/dashboard');
    });
});
