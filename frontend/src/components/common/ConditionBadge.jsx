import React from 'react';

const CONDITION_CONFIG = {
  new: { label: 'New', colorClass: 'badge-blue' },
  like_new: { label: 'Like New', colorClass: 'badge-green' },
  very_good: { label: 'Very Good', colorClass: 'badge-green' },
  good: { label: 'Good', colorClass: 'badge-amber' },
  acceptable: { label: 'Acceptable', colorClass: 'badge-amber' },
  poor: { label: 'Poor', colorClass: 'badge-red' },
};

/**
 * ConditionBadge — colored badge showing book condition.
 * @param {object} props
 * @param {string} props.condition - One of the condition keys
 */
export default function ConditionBadge({ condition }) {
  const config = CONDITION_CONFIG[condition] ?? { label: condition ?? 'Unknown', colorClass: 'badge-gray' };

  return (
    <span className={`badge ${config.colorClass}`}>
      {config.label}
    </span>
  );
}

export { CONDITION_CONFIG };
