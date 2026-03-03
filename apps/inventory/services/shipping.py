"""
Shipping cost estimator using USPS Media Mail heuristics.

USPS Media Mail rates (as of 2024, update annually):
- First pound: $4.63
- Each additional pound: $0.53

Weight heuristic: ~1 lb per 400 pages (rough average for paperbacks/hardcovers).
Minimum assumed weight: 0.5 lb.
"""

BASE_RATE_LOW = 4.00   # Conservative low estimate ($/first lb)
BASE_RATE_HIGH = 5.00  # Conservative high estimate ($/first lb)
PER_LB_LOW = 0.50      # Additional lbs, low estimate
PER_LB_HIGH = 0.60     # Additional lbs, high estimate
PAGES_PER_LB = 400.0   # Heuristic: pages per pound
MIN_WEIGHT_LB = 0.5    # Minimum assumed weight


def estimate_shipping(page_count: int | None) -> dict:
    """
    Estimate USPS Media Mail shipping cost from page count.

    Returns a dict with:
      - weight_lbs: estimated weight
      - low: low cost estimate (USD)
      - high: high cost estimate (USD)
      - display: human-readable string
      - disclaimer: copy to show users
    """
    if page_count and page_count > 0:
        weight_lbs = max(page_count / PAGES_PER_LB, MIN_WEIGHT_LB)
    else:
        weight_lbs = MIN_WEIGHT_LB  # Default for unknown page count

    extra_lbs = max(weight_lbs - 1.0, 0)

    low = BASE_RATE_LOW + extra_lbs * PER_LB_LOW
    high = BASE_RATE_HIGH + extra_lbs * PER_LB_HIGH

    # Round to nearest $0.25 for cleanliness
    low_rounded = round(low * 4) / 4
    high_rounded = round(high * 4) / 4

    # Ensure at least a $0.50 spread
    if high_rounded <= low_rounded:
        high_rounded = low_rounded + 0.50

    display = f'${low_rounded:.2f}–${high_rounded:.2f}'

    return {
        'weight_lbs': round(weight_lbs, 2),
        'low': low_rounded,
        'high': high_rounded,
        'display': display,
        'disclaimer': (
            f'Shipping is the sender\'s responsibility. USPS Media Mail is the most '
            f'affordable option for books — we estimate this shipment around '
            f'{display} — but you\'re free to use any carrier or method you prefer. '
            f'This is only a rough estimate.'
        ),
    }
