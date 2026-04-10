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
});
