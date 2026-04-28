import React from 'react';
import Tooltip from './Tooltip.jsx';

const CONDITION_CONFIG = {
  new: { label: 'New', colorClass: 'badge-blue', description: 'Brand new, unread, and unused. Typically in original packaging.' },
  like_new: { label: 'Like New', colorClass: 'badge-green', description: 'Unread or nearly unread. No marks, creases, or wear. May have been shelved but never opened.' },
  very_good: { label: 'Very Good', colorClass: 'badge-green', description: 'Minimal signs of use. Spine may show light wear. No writing or highlighting.' },
  good: { label: 'Good', colorClass: 'badge-amber', description: 'Some wear visible — light creasing, minor shelf wear. No missing pages. Writing or highlights possible.' },
  acceptable: { label: 'Acceptable', colorClass: 'badge-amber', description: 'Heavily worn but complete and readable. May have writing, highlighting, or a broken spine.' },
  poor: { label: 'Poor', colorClass: 'badge-red', description: 'Significant damage but text is intact. May have missing cover, torn pages, or heavy marking.' },
};

/**
 * ConditionBadge — colored badge showing book condition with a tooltip description.
 * @param {object} props
 * @param {string} props.condition - One of the condition keys
 */
export default function ConditionBadge({ condition }) {
  const config = CONDITION_CONFIG[condition] ?? { label: condition ?? 'Unknown', colorClass: 'badge-gray' };

  const badge = (
    <span className={`badge ${config.colorClass}`}>
      {config.label}
    </span>
  );

  if (!config.description) {
    return badge;
  }

  return (
    <Tooltip content={config.description}>
      {badge}
    </Tooltip>
  );
}

export { CONDITION_CONFIG };
