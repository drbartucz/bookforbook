import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ErrorMessage from './ErrorMessage.jsx';

describe('ErrorMessage', () => {
    it('renders a string error message', () => {
        render(<ErrorMessage error="Something went wrong" />);
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });

    it('extracts detail from an axios-style error object', () => {
        const error = { response: { data: { detail: 'Invalid credentials.' } } };
        render(<ErrorMessage error={error} />);
        expect(screen.getByText('Invalid credentials.')).toBeInTheDocument();
    });

    it('extracts non_field_errors from an axios-style error', () => {
        const error = { response: { data: { non_field_errors: ['Email not verified.'] } } };
        render(<ErrorMessage error={error} />);
        expect(screen.getByText('Email not verified.')).toBeInTheDocument();
    });

    it('falls back to error.message when no response data', () => {
        const error = { message: 'Network Error' };
        render(<ErrorMessage error={error} />);
        expect(screen.getByText('Network Error')).toBeInTheDocument();
    });

    it('shows default text when error is null', () => {
        render(<ErrorMessage error={null} />);
        expect(screen.getByText('An unexpected error occurred.')).toBeInTheDocument();
    });

    it('renders retry button when onRetry is provided', () => {
        const onRetry = vi.fn();
        render(<ErrorMessage error="Oops" onRetry={onRetry} />);
        expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
    });

    it('calls onRetry when retry button is clicked', async () => {
        const onRetry = vi.fn();
        render(<ErrorMessage error="Oops" onRetry={onRetry} />);
        await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
        expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it('uses custom retryLabel when provided', () => {
        render(<ErrorMessage error="Oops" onRetry={() => { }} retryLabel="Reload" />);
        expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument();
    });

    it('does not render retry button when onRetry is omitted', () => {
        render(<ErrorMessage error="Oops" />);
        expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });

    it('extracts message field from response data', () => {
        const error = { response: { data: { message: 'Custom message here.' } } };
        render(<ErrorMessage error={error} />);
        expect(screen.getByText('Custom message here.')).toBeInTheDocument();
    });

    it('returns raw string response data when data is a string', () => {
        const error = { response: { data: 'Raw string error.' } };
        render(<ErrorMessage error={error} />);
        expect(screen.getByText('Raw string error.')).toBeInTheDocument();
    });

    it('extracts first field error as array from response data', () => {
        const error = { response: { data: { username: ['This username is taken.'] } } };
        render(<ErrorMessage error={error} />);
        expect(screen.getByText('username: This username is taken.')).toBeInTheDocument();
    });

    it('extracts first field error as string from response data', () => {
        const error = { response: { data: { email: 'Invalid email format.' } } };
        render(<ErrorMessage error={error} />);
        expect(screen.getByText('email: Invalid email format.')).toBeInTheDocument();
    });

    it('falls back to default message when error has no message property', () => {
        render(<ErrorMessage error={{}} />);
        expect(screen.getByText('An unexpected error occurred.')).toBeInTheDocument();
    });
});
