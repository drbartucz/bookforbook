import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach } from 'vitest';

import Toast from './Toast.jsx';
import useNotificationStore from '../../hooks/useNotification.js';

describe('Toast', () => {
    beforeEach(() => {
        useNotificationStore.setState({ notifications: [] });
    });

    it('renders nothing when no notifications', () => {
        const { container } = render(<Toast />);
        const toasts = container.querySelectorAll('[role="alert"]');
        expect(toasts).toHaveLength(0);
    });

    it('renders multiple notifications with type styles', () => {
        useNotificationStore.setState({
            notifications: [
                { id: 1, message: 'Success message', type: 'success' },
                { id: 2, message: 'Error message', type: 'error' },
            ],
        });

        render(<Toast />);

        expect(screen.getByText('Success message')).toBeInTheDocument();
        expect(screen.getByText('Error message')).toBeInTheDocument();
    });

    it('removes notification when close button clicked', async () => {
        const user = userEvent.setup();
        useNotificationStore.setState({
            notifications: [{ id: 1, message: 'Test message', type: 'info' }],
        });

        render(<Toast />);

        const closeButton = screen.getByLabelText('Close notification');
        await user.click(closeButton);

        expect(screen.queryByText('Test message')).not.toBeInTheDocument();
    });

    it('displays warning type for automatic logout', () => {
        useNotificationStore.setState({
            notifications: [
                { id: 1, message: 'You have been automatically logged out.', type: 'warning' },
            ],
        });

        render(<Toast />);

        const toast = screen.getByText('You have been automatically logged out.').closest('[role="alert"]');
        expect(toast).toBeInTheDocument();
        // CSS module transforms 'warning' class to a hashed name, so just check the className contains 'warning'
        expect(toast.className).toMatch(/warning/);
    });
});
