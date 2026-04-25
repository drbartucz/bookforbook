import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

import { renderWithProviders } from '../../test/renderWithProviders.jsx';
import AddressPromptModal from './AddressPromptModal.jsx';

vi.mock('../../services/api.js', () => ({
    users: {
        verifyAddress: vi.fn(),
    },
}));

import { users } from '../../services/api.js';

describe('AddressPromptModal', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders nothing when open=false', () => {
        renderWithProviders(<AddressPromptModal open={false} onClose={vi.fn()} />);
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('renders the prompt step when open=true', () => {
        renderWithProviders(<AddressPromptModal open={true} onClose={vi.fn()} />);
        expect(screen.getByRole('dialog')).toBeInTheDocument();
        expect(screen.getByText(/would you like to add your address now/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /not now/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /add address/i })).toBeInTheDocument();
    });

    it('calls onClose when "Not now" is clicked', async () => {
        const onClose = vi.fn();
        renderWithProviders(<AddressPromptModal open={true} onClose={onClose} />);
        await userEvent.click(screen.getByRole('button', { name: /not now/i }));
        expect(onClose).toHaveBeenCalled();
    });

    it('advances to the verify form when "Add address" is clicked', async () => {
        renderWithProviders(<AddressPromptModal open={true} onClose={vi.fn()} />);
        await userEvent.click(screen.getByRole('button', { name: /add address/i }));
        expect(screen.getByText(/verify shipping address/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/address line 1/i)).toBeInTheDocument();
    });

    it('closes when backdrop is clicked', async () => {
        const onClose = vi.fn();
        const { container } = renderWithProviders(
            <AddressPromptModal open={true} onClose={onClose} />
        );
        const backdrop = container.querySelector('[role="presentation"]');
        // Simulate a click directly on the backdrop (not on a child)
        await userEvent.pointer({ target: backdrop, keys: '[MouseLeft]' });
        expect(onClose).toHaveBeenCalled();
    });

    describe('address form', () => {
        async function openVerifyStep(onClose = vi.fn()) {
            renderWithProviders(<AddressPromptModal open={true} onClose={onClose} />);
            await userEvent.click(screen.getByRole('button', { name: /add address/i }));
        }

        it('submits the form and calls onClose on success', async () => {
            const onClose = vi.fn();
            users.verifyAddress.mockResolvedValue({ data: {} });
            await openVerifyStep(onClose);

            await userEvent.type(screen.getByLabelText(/full name/i), 'Jane Doe');
            await userEvent.type(screen.getByLabelText(/address line 1/i), '123 Main St');
            await userEvent.type(screen.getByLabelText(/city/i), 'Denver');
            await userEvent.type(screen.getByLabelText(/state/i), 'CO');
            await userEvent.type(screen.getByLabelText(/zip/i), '80202');
            await userEvent.click(screen.getByRole('button', { name: /verify with usps/i }));

            await waitFor(() => expect(onClose).toHaveBeenCalled());
        });

        it('shows an error message on API failure with detail', async () => {
            users.verifyAddress.mockRejectedValue({
                response: { data: { detail: 'Address not found.' } },
            });
            await openVerifyStep();

            await userEvent.type(screen.getByLabelText(/full name/i), 'Jane Doe');
            await userEvent.type(screen.getByLabelText(/address line 1/i), '123 Main St');
            await userEvent.type(screen.getByLabelText(/city/i), 'Denver');
            await userEvent.type(screen.getByLabelText(/state/i), 'CO');
            await userEvent.type(screen.getByLabelText(/zip/i), '80202');
            await userEvent.click(screen.getByRole('button', { name: /verify with usps/i }));

            expect(await screen.findByText(/address not found/i)).toBeInTheDocument();
        });

        it('shows a generic error when there is no detail in the response', async () => {
            users.verifyAddress.mockRejectedValue(new Error('network'));
            await openVerifyStep();

            await userEvent.type(screen.getByLabelText(/full name/i), 'Jane Doe');
            await userEvent.type(screen.getByLabelText(/address line 1/i), '123 Main St');
            await userEvent.type(screen.getByLabelText(/city/i), 'Denver');
            await userEvent.type(screen.getByLabelText(/state/i), 'CO');
            await userEvent.type(screen.getByLabelText(/zip/i), '80202');
            await userEvent.click(screen.getByRole('button', { name: /verify with usps/i }));

            expect(
                await screen.findByText(/unable to verify address/i)
            ).toBeInTheDocument();
        });

        it('disables the submit button while verifying', async () => {
            let resolve;
            users.verifyAddress.mockReturnValue(new Promise((r) => { resolve = r; }));
            await openVerifyStep();

            await userEvent.type(screen.getByLabelText(/full name/i), 'Jane');
            await userEvent.type(screen.getByLabelText(/address line 1/i), '1 St');
            await userEvent.type(screen.getByLabelText(/city/i), 'Denver');
            await userEvent.type(screen.getByLabelText(/state/i), 'CO');
            await userEvent.type(screen.getByLabelText(/zip/i), '80202');
            await userEvent.click(screen.getByRole('button', { name: /verify with usps/i }));

            expect(await screen.findByRole('button', { name: /verifying/i })).toBeDisabled();
            resolve({ data: {} });
        });

        it('calls onClose when "Skip for now" is clicked', async () => {
            const onClose = vi.fn();
            await openVerifyStep(onClose);
            await userEvent.click(screen.getByRole('button', { name: /skip for now/i }));
            expect(onClose).toHaveBeenCalled();
        });

        it('updates the state field to uppercase', async () => {
            await openVerifyStep();
            const stateInput = screen.getByLabelText(/state/i);
            await userEvent.type(stateInput, 'co');
            expect(stateInput.value).toBe('CO');
        });
    });
});
