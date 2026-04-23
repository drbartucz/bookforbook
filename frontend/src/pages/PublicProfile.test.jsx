import React from 'react';
import { screen } from '@testing-library/react';
import { vi } from 'vitest';

import { renderWithProviders } from '../test/renderWithProviders.jsx';
import PublicProfile from './PublicProfile.jsx';
import useAuth from '../hooks/useAuth.js';
import { useParams } from 'react-router-dom';

vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual('react-router-dom');
    return {
        ...actual,
        useParams: vi.fn(),
    };
});

vi.mock('../hooks/useAuth.js', () => ({
    default: vi.fn(),
}));

vi.mock('../services/api.js', () => ({
    users: {
        getPublicProfile: vi.fn(),
        getUserRatings: vi.fn(),
        getMe: vi.fn(),
    },
    institutions: {
        getWantedList: vi.fn(),
    },
}));

import { institutions, users } from '../services/api.js';

describe('PublicProfile page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        useParams.mockReturnValue({ id: 'institution-1' });
        useAuth.mockReturnValue({ isAuthenticated: false, user: null });
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

    it('shows shipping address when viewing your own profile', async () => {
        useParams.mockReturnValue({ id: 'user-1' });
        useAuth.mockReturnValue({ isAuthenticated: true, user: { id: 'user-1' } });

        users.getPublicProfile.mockResolvedValue({
            data: {
                id: 'user-1',
                username: 'reader',
                account_type: 'individual',
                is_verified: true,
                total_trades: 3,
            },
        });
        users.getUserRatings.mockResolvedValue({ data: [] });
        users.getMe.mockResolvedValue({
            data: {
                id: 'user-1',
                full_name: 'Jane Reader',
                address_line_1: '123 Main St',
                address_line_2: 'Apt 2',
                city: 'Portland',
                state: 'OR',
                zip_code: '97201',
                address_verification_status: 'verified',
            },
        });

        renderWithProviders(<PublicProfile />);

        expect(await screen.findByText('Shipping Address')).toBeInTheDocument();
        expect(screen.getByText('123 Main St')).toBeInTheDocument();
        expect(screen.getByText('Portland, OR 97201')).toBeInTheDocument();
        expect(screen.getByText('Edit address')).toHaveAttribute('href', '/account');
    });

    it('does not show shipping address on another user profile', async () => {
        useParams.mockReturnValue({ id: 'institution-1' });
        useAuth.mockReturnValue({ isAuthenticated: true, user: { id: 'user-1' } });

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
        institutions.getWantedList.mockResolvedValue({ data: [] });

        renderWithProviders(<PublicProfile />);

        expect(await screen.findByText('@central-library')).toBeInTheDocument();
        expect(screen.queryByText('Shipping Address')).not.toBeInTheDocument();
        expect(users.getMe).not.toHaveBeenCalled();
    });
});