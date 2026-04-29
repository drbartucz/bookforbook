import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import AppErrorBoundary from './AppErrorBoundary.jsx';

// Suppress React's error boundary console.error noise in test output
beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => { });
});
afterEach(() => {
    console.error.mockRestore();
});

function Bomb({ shouldThrow }) {
    if (shouldThrow) {
        throw new Error('Test explosion');
    }
    return <div data-testid="child">All good</div>;
}

describe('AppErrorBoundary', () => {
    it('renders children when no error is thrown', () => {
        render(
            <AppErrorBoundary>
                <Bomb shouldThrow={false} />
            </AppErrorBoundary>
        );
        expect(screen.getByTestId('child')).toBeInTheDocument();
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('renders the fallback UI when a child throws', () => {
        render(
            <AppErrorBoundary>
                <Bomb shouldThrow={true} />
            </AppErrorBoundary>
        );
        expect(screen.getByRole('alert')).toBeInTheDocument();
        expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
        expect(screen.getByText(/please refresh the page/i)).toBeInTheDocument();
        expect(screen.queryByTestId('child')).not.toBeInTheDocument();
    });

    it('"Try again" button resets the error boundary and re-renders children', async () => {
        // When the boundary shows its fallback, the throwing child is unmounted.
        // Strategy: rerender with a non-throwing child (updates `children` prop on
        // the still-errored boundary), THEN click "Try again" so the reset sees
        // a safe child and successfully renders it.
        const { rerender } = render(
            <AppErrorBoundary>
                <Bomb shouldThrow={true} />
            </AppErrorBoundary>
        );
        expect(screen.getByRole('alert')).toBeInTheDocument();

        // Swap in a non-throwing child while boundary is still in error state
        rerender(
            <AppErrorBoundary>
                <Bomb shouldThrow={false} />
            </AppErrorBoundary>
        );
        expect(screen.getByRole('alert')).toBeInTheDocument(); // still fallback

        // Now reset — boundary renders the safe child
        await userEvent.click(screen.getByRole('button', { name: /try again/i }));

        expect(screen.getByTestId('child')).toBeInTheDocument();
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
});
