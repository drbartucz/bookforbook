import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Contact from './Contact.jsx';

// Mock Turnstile
vi.mock('@marsidev/react-turnstile', () => ({
  Turnstile: ({ onSuccess }) => {
    // We'll manually trigger onSuccess in the test when we want to "verify"
    return <div data-testid="turnstile-mock" onClick={() => onSuccess('test-token')} />;
  },
}));

// Mock the CSS module
vi.mock('./Contact.module.css', () => ({
  default: {
    container: 'container',
    formWrapper: 'formWrapper',
    header: 'header',
    title: 'title',
    subtitle: 'subtitle',
    form: 'form',
    field: 'field',
    error: 'error',
    captchaWrapper: 'captchaWrapper',
  },
}));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
});

const renderWithClient = (ui) => {
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  );
};

describe('Contact Page', () => {
  it('renders correctly and submit button is disabled initially', () => {
    renderWithClient(<Contact />);
    
    expect(screen.getByText('Contact Us')).toBeInTheDocument();
    expect(screen.getByLabelText(/Name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Email Address/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Message/i)).toBeInTheDocument();
    
    const submitButton = screen.getByRole('button', { name: /Send Message/i });
    expect(submitButton).toBeDisabled();
  });

  it('enables submit button after Turnstile success', async () => {
    renderWithClient(<Contact />);
    
    const turnstile = screen.getByTestId('turnstile-mock');
    fireEvent.click(turnstile);
    
    const submitButton = screen.getByRole('button', { name: /Send Message/i });
    await waitFor(() => expect(submitButton).not.toBeDisabled());
  });

  it('shows validation errors for empty fields', async () => {
    renderWithClient(<Contact />);
    
    // Enable button first
    fireEvent.click(screen.getByTestId('turnstile-mock'));
    
    const submitButton = screen.getByRole('button', { name: /Send Message/i });
    fireEvent.click(submitButton);
    
    expect(await screen.findByText('Name is required')).toBeInTheDocument();
    expect(await screen.findByText('Email is required')).toBeInTheDocument();
    expect(await screen.findByText('Message is required')).toBeInTheDocument();
  });
});
