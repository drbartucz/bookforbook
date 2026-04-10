import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Pagination from './Pagination.jsx';

describe('Pagination', () => {
    it('renders nothing when totalPages is 1', () => {
        const { container } = render(
            <Pagination page={1} totalPages={1} onPageChange={() => { }} />
        );
        expect(container.firstChild).toBeNull();
    });

    it('renders nothing when totalPages is 0', () => {
        const { container } = render(
            <Pagination page={1} totalPages={0} onPageChange={() => { }} />
        );
        expect(container.firstChild).toBeNull();
    });

    it('renders page number buttons when totalPages > 1', () => {
        render(<Pagination page={2} totalPages={3} onPageChange={() => { }} />);
        expect(screen.getByText('1')).toBeInTheDocument();
        expect(screen.getByText('2')).toBeInTheDocument();
        expect(screen.getByText('3')).toBeInTheDocument();
    });

    it('disables the Prev button on the first page', () => {
        render(<Pagination page={1} totalPages={5} onPageChange={() => { }} />);
        expect(screen.getByLabelText('Previous page')).toBeDisabled();
    });

    it('disables the Next button on the last page', () => {
        render(<Pagination page={5} totalPages={5} onPageChange={() => { }} />);
        expect(screen.getByLabelText('Next page')).toBeDisabled();
    });

    it('marks the current page button with aria-current="page"', () => {
        render(<Pagination page={2} totalPages={3} onPageChange={() => { }} />);
        expect(screen.getByRole('button', { name: '2' })).toHaveAttribute('aria-current', 'page');
    });

    it('calls onPageChange with next page when Next is clicked', async () => {
        const onPageChange = vi.fn();
        render(<Pagination page={2} totalPages={5} onPageChange={onPageChange} />);
        await userEvent.click(screen.getByLabelText('Next page'));
        expect(onPageChange).toHaveBeenCalledWith(3);
    });

    it('calls onPageChange with previous page when Prev is clicked', async () => {
        const onPageChange = vi.fn();
        render(<Pagination page={3} totalPages={5} onPageChange={onPageChange} />);
        await userEvent.click(screen.getByLabelText('Previous page'));
        expect(onPageChange).toHaveBeenCalledWith(2);
    });

    it('calls onPageChange with clicked page number', async () => {
        const onPageChange = vi.fn();
        render(<Pagination page={1} totalPages={3} onPageChange={onPageChange} />);
        await userEvent.click(screen.getByRole('button', { name: '3' }));
        expect(onPageChange).toHaveBeenCalledWith(3);
    });

    it('disables all buttons when disabled prop is true', () => {
        render(<Pagination page={2} totalPages={3} onPageChange={() => { }} disabled />);
        screen.getAllByRole('button').forEach((btn) => {
            expect(btn).toBeDisabled();
        });
    });
});
