import React from 'react';
import { render, screen } from '@testing-library/react';
import ConditionBadge, { CONDITION_CONFIG } from './ConditionBadge.jsx';

describe('ConditionBadge', () => {
  it.each(Object.entries(CONDITION_CONFIG))(
    'renders correct label for condition "%s"',
    (condition, { label }) => {
      render(<ConditionBadge condition={condition} />);
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  );

  it('renders the condition string itself for an unknown condition', () => {
    render(<ConditionBadge condition="worn" />);
    expect(screen.getByText('worn')).toBeInTheDocument();
  });

  it('renders "Unknown" when condition is null/undefined', () => {
    render(<ConditionBadge condition={undefined} />);
    expect(screen.getByText('Unknown')).toBeInTheDocument();
  });

  it('applies badge-green class for like_new condition', () => {
    render(<ConditionBadge condition="like_new" />);
    expect(screen.getByText('Like New').className).toContain('badge-green');
  });

  it('applies badge-amber class for good condition', () => {
    render(<ConditionBadge condition="good" />);
    expect(screen.getByText('Good').className).toContain('badge-amber');
  });
});
