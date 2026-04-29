import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import { renderWithProviders } from '../test/renderWithProviders.jsx';
import Register from './Register.jsx';

vi.mock('../services/api.js', () => ({
    auth: {
        register: vi.fn(),
    },
}));

import { auth as authApi } from '../services/api.js';

beforeEach(() => {
    vi.clearAllMocks();
});

async function fillForm(options = {}) {
    const {
        email = 'newuser@example.com',
        username = 'newuser',
        password = 'securepass',
        confirmPassword = 'securepass',
    } = options;

    await userEvent.type(screen.getByLabelText(/email address/i), email);
    await userEvent.type(screen.getByRole('textbox', { name: /^username/i }), username);
    await userEvent.type(screen.getByLabelText(/^password$/i), password);
    await userEvent.type(screen.getByLabelText(/confirm password/i), confirmPassword);
}

describe('Register page', () => {
    it('renders registration form fields', () => {
        renderWithProviders(<Register />);
        expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
        expect(screen.getByRole('textbox', { name: /^username/i })).toBeInTheDocument();
        expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
    });

    it('shows "Please check your email" screen on successful registration', async () => {
        authApi.register.mockResolvedValueOnce({ data: {} });

        renderWithProviders(<Register />);
        await fillForm();
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText(/Please check your email/i)).toBeInTheDocument();
        });
        expect(authApi.register).toHaveBeenCalledWith(expect.objectContaining({
            account_type: 'individual',
            institution_name: '',
            institution_url: '',
        }));
    });

    it('renders institution fields and submits institution payload for library account', async () => {
        authApi.register.mockResolvedValueOnce({ data: {} });

        renderWithProviders(<Register />);
        await userEvent.click(screen.getByLabelText(/library/i));

        expect(screen.getByLabelText(/institution name/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/institution website/i)).toBeInTheDocument();

        await fillForm();
        await userEvent.type(screen.getByLabelText(/institution name/i), 'City Library');
        await userEvent.type(screen.getByLabelText(/institution website/i), 'https://library.example.org');
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(authApi.register).toHaveBeenCalledWith(expect.objectContaining({
                account_type: 'library',
                institution_name: 'City Library',
                institution_url: 'https://library.example.org',
            }));
        });
    });

    it('shows Go to sign in link on success screen', async () => {
        authApi.register.mockResolvedValueOnce({ data: {} });

        renderWithProviders(<Register />);
        await fillForm();
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByRole('link', { name: /go to sign in/i })).toBeInTheDocument();
        });
    });

    it('shows server error detail on registration failure', async () => {
        authApi.register.mockRejectedValueOnce({
            response: { data: { detail: 'A user with this email already exists.' } },
        });

        renderWithProviders(<Register />);
        await fillForm();
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText('A user with this email already exists.')).toBeInTheDocument();
        });
    });

    it('shows email field error from server', async () => {
        authApi.register.mockRejectedValueOnce({
            response: { data: { email: ['Enter a valid email address.'] } },
        });

        renderWithProviders(<Register />);
        await fillForm();
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText(/Email:/)).toBeInTheDocument();
        });
    });

    it('shows client-side validation error when passwords do not match', async () => {
        renderWithProviders(<Register />);
        await fillForm({ password: 'password1', confirmPassword: 'password2' });
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText('Passwords do not match.')).toBeInTheDocument();
        });
    });

    it('shows client-side validation error for short username', async () => {
        renderWithProviders(<Register />);
        await fillForm({ username: 'ab' });
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText('Must be at least 3 characters.')).toBeInTheDocument();
        });
    });

    it('shows URL validation error for non-http institution website', async () => {
        renderWithProviders(<Register />);
        await userEvent.click(screen.getByLabelText(/library/i));
        await fillForm();
        await userEvent.type(screen.getByLabelText(/institution name/i), 'Test Library');
        await userEvent.type(screen.getByLabelText(/institution website/i), 'ftp://library.example.org');
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));
        await waitFor(() => {
            expect(screen.getByText(/use an http/i)).toBeInTheDocument();
        });
    });

    it('shows URL validation error for completely invalid institution website', async () => {
        renderWithProviders(<Register />);
        await userEvent.click(screen.getByLabelText(/library/i));
        await fillForm();
        await userEvent.type(screen.getByLabelText(/institution name/i), 'Test Library');
        await userEvent.type(screen.getByLabelText(/institution website/i), 'not a url at all');
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));
        await waitFor(() => {
            expect(screen.getByText(/enter a valid url/i)).toBeInTheDocument();
        });
    });

    it('shows username field error from server', async () => {
        authApi.register.mockRejectedValueOnce({
            response: { data: { username: ['This username is already taken.'] } },
        });

        renderWithProviders(<Register />);
        await fillForm();
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText(/Username:/)).toBeInTheDocument();
        });
    });

    it('shows password field error from server', async () => {
        authApi.register.mockRejectedValueOnce({
            response: { data: { password: ['Password is too common.'] } },
        });

        renderWithProviders(<Register />);
        await fillForm();
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText(/Password:/)).toBeInTheDocument();
        });
    });

    it('shows fallback error when no recognized field in server response', async () => {
        authApi.register.mockRejectedValueOnce({
            response: { data: { non_field_errors: ['Something went wrong.'] } },
        });

        renderWithProviders(<Register />);
        await fillForm();
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText(/Registration failed. Please check/i)).toBeInTheDocument();
        });
    });

    it('shows fallback error when no response data available', async () => {
        authApi.register.mockRejectedValueOnce(new Error('Network Error'));

        renderWithProviders(<Register />);
        await fillForm();
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText('Registration failed. Please try again.')).toBeInTheDocument();
        });
    });

    it('shows institution name validation error when name is missing', async () => {
        renderWithProviders(<Register />);
        await userEvent.click(screen.getByLabelText(/library/i));
        await fillForm();
        // Do not type institution name — leave it empty
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText('Institution name is required.')).toBeInTheDocument();
        });
    });

    it('disables submit button while submitting', async () => {
        authApi.register.mockReturnValueOnce(new Promise(() => { }));

        renderWithProviders(<Register />);
        await fillForm();
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByRole('button', { name: /creating/i })).toBeDisabled();
        });
    });

    it('shows plain string response as server error (covers typeof resData === "string" branch)', async () => {
        authApi.register.mockRejectedValueOnce({
            response: { data: 'Internal Server Error' },
        });

        renderWithProviders(<Register />);
        await fillForm();
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText('Internal Server Error')).toBeInTheDocument();
        });
    });

    it('shows email string error directly when resData.email is a string (covers Array.isArray false branch)', async () => {
        authApi.register.mockRejectedValueOnce({
            response: { data: { email: 'That email is already registered.' } },
        });

        renderWithProviders(<Register />);
        await fillForm();
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText(/Email: That email is already registered/)).toBeInTheDocument();
        });
    });

    it('shows username string error directly when resData.username is a string', async () => {
        authApi.register.mockRejectedValueOnce({
            response: { data: { username: 'That username is taken.' } },
        });

        renderWithProviders(<Register />);
        await fillForm();
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText(/Username: That username is taken/)).toBeInTheDocument();
        });
    });

    it('shows password string error directly when resData.password is a string', async () => {
        authApi.register.mockRejectedValueOnce({
            response: { data: { password: 'Password is too weak.' } },
        });

        renderWithProviders(<Register />);
        await fillForm();
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByText(/Password: Password is too weak/)).toBeInTheDocument();
        });
    });

    it('applies error class to email field when email format fails client validation', async () => {
        renderWithProviders(<Register />);
        await fillForm({ email: 'notanemail' });
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByLabelText(/email address/i).className).toContain('error');
        });
    });

    it('applies error class to password field when password is too short', async () => {
        renderWithProviders(<Register />);
        await fillForm({ password: 'short1', confirmPassword: 'short1' });
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(screen.getByLabelText(/^password$/i).className).toContain('error');
        });
    });

    it('accepts http:// institution website URL (covers left side of || in protocol check)', async () => {
        authApi.register.mockResolvedValueOnce({ data: {} });

        renderWithProviders(<Register />);
        await userEvent.click(screen.getByLabelText(/library/i));
        await fillForm();
        await userEvent.type(screen.getByLabelText(/institution name/i), 'City Library');
        await userEvent.type(screen.getByLabelText(/institution website/i), 'http://library.example.org');
        await userEvent.click(screen.getByRole('button', { name: /create account/i }));

        await waitFor(() => {
            expect(authApi.register).toHaveBeenCalledWith(expect.objectContaining({
                institution_url: 'http://library.example.org',
            }));
        });
    });
});
