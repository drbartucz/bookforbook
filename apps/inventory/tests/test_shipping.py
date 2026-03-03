"""
Unit tests for the shipping estimate utility.
"""
import pytest

from apps.inventory.services.shipping import estimate_shipping


class TestShippingEstimate:
    def test_estimate_thin_book(self):
        # 200 pages ≈ 0.5 lb (min weight)
        result = estimate_shipping(200)
        assert result['weight_lbs'] == 0.5
        assert result['low'] >= 4.0
        assert result['high'] > result['low']
        assert '$' in result['display']

    def test_estimate_typical_book(self):
        # 400 pages ≈ 1 lb
        result = estimate_shipping(400)
        assert result['weight_lbs'] == 1.0
        assert 4.0 <= result['low'] <= 5.0

    def test_estimate_thick_book(self):
        # 800 pages ≈ 2 lbs
        result = estimate_shipping(800)
        assert result['weight_lbs'] == 2.0
        assert result['low'] > 4.0

    def test_estimate_none_page_count(self):
        # Unknown page count → default minimum weight
        result = estimate_shipping(None)
        assert result['weight_lbs'] == 0.5
        assert result['low'] >= 4.0

    def test_estimate_zero_page_count(self):
        result = estimate_shipping(0)
        assert result['weight_lbs'] == 0.5

    def test_estimate_has_disclaimer(self):
        result = estimate_shipping(300)
        assert 'USPS Media Mail' in result['disclaimer']
        assert 'Shipping is the sender' in result['disclaimer']

    def test_estimate_spread_at_least_50_cents(self):
        result = estimate_shipping(400)
        assert result['high'] - result['low'] >= 0.50
