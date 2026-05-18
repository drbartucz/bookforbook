import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import About from './About.jsx';

// Mock the CSS module
vi.mock('./About.module.css', () => ({
  default: {
    container: 'container',
    hero: 'hero',
    title: 'title',
    subtitle: 'subtitle',
    section: 'section',
    grid: 'grid',
    card: 'card',
    icon: 'icon',
    faqSection: 'faqSection',
    faqTitle: 'faqTitle',
    accordionRoot: 'accordionRoot',
    accordionItem: 'accordionItem',
    accordionHeader: 'accordionHeader',
    accordionTrigger: 'accordionTrigger',
    chevron: 'chevron',
    accordionContent: 'accordionContent',
    accordionContentInner: 'accordionContentInner',
  },
}));

describe('About Page', () => {
  it('renders the about page content', () => {
    render(<About />);

    expect(screen.getByText(/Create an account/i)).toBeInTheDocument();
    expect(screen.getByText(/rate your trade partner/i)).toBeInTheDocument();
    expect(screen.getByText('Sustainable')).toBeInTheDocument();
    expect(screen.getByText('Connections')).toBeInTheDocument();
    expect(screen.getByText('Cost-Effective')).toBeInTheDocument();
  });

  it('renders the FAQ section', () => {
    render(<About />);

    expect(screen.getByText('Frequently Asked Questions')).toBeInTheDocument();
    expect(screen.getByText('How does BookForBook work?')).toBeInTheDocument();
    expect(screen.getByText('How does shipping work?')).toBeInTheDocument();
  });

  it('toggles FAQ items when clicked', async () => {
    render(<About />);

    const trigger = screen.getByText('How does BookForBook work?');

    // Radix Accordion usually sets data-state="closed" initially
    const item = trigger.closest('[data-state]');
    expect(item).toHaveAttribute('data-state', 'closed');

    fireEvent.click(trigger);

    // After click, it should be open
    expect(item).toHaveAttribute('data-state', 'open');
    expect(screen.getByText(/BookForBook is a free book swap platform/i)).toBeVisible();
  });
});
