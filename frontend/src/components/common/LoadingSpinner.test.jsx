import React from 'react';
import { render, screen } from '@testing-library/react';
import LoadingSpinner from './LoadingSpinner.jsx';

describe('LoadingSpinner', () => {
  it('renders with default accessible label', () => {
    render(<LoadingSpinner />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Loading...');
  });

  it('uses a custom label when provided', () => {
    render(<LoadingSpinner label="Fetching books..." />);
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Fetching books...');
  });

  it('includes sr-only span with label text', () => {
    render(<LoadingSpinner label="Please wait" />);
    expect(screen.getByText('Please wait')).toBeInTheDocument();
  });

  it('does not apply center class by default', () => {
    render(<LoadingSpinner />);
    const wrapper = screen.getByRole('status');
    expect(wrapper.className).not.toMatch(/center/);
  });

  it('applies center class when center prop is true', () => {
    render(<LoadingSpinner center />);
    const wrapper = screen.getByRole('status');
    expect(wrapper.className).toMatch(/center/);
  });
});
