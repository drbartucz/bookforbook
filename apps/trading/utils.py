import re

# Heuristic patterns — not exhaustive, cover the most common US carrier formats.
_TRACKING_PATTERNS = [
    re.compile(r'^(9[0-5])\d{20}$'),        # USPS
    re.compile(r'^1Z[0-9A-Z]{16}$'),          # UPS
    re.compile(r'^(?:96|98)\d{16}$'),         # FedEx (carrier-specific prefixes)
    re.compile(r'^[0-9]{15}$'),               # FedEx 15-digit express
]


def is_valid_tracking_number(value: str) -> bool:
    if not value:
        return False
    normalized = value.strip().upper()
    return any(p.match(normalized) for p in _TRACKING_PATTERNS)
