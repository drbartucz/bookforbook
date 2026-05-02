import pytest
from apps.inventory.services.shipping import estimate_shipping

def test_estimate_shipping_unknown():
    res = estimate_shipping(None)
    assert res['weight_lbs'] == 0.5
    assert res['low'] == 4.00
    assert res['high'] == 5.00 # Base rate high is 5.00

def test_estimate_shipping_small():
    res = estimate_shipping(200) # Should hit min weight
    assert res['weight_lbs'] == 0.5
    assert res['low'] == 4.00

def test_estimate_shipping_large():
    # 800 pages -> 2.0 lbs
    # Extra lbs = 1.0
    # Low = 4.0 + 1.0 * 0.50 = 4.50
    # High = 5.0 + 1.0 * 0.60 = 5.60 -> rounded to 5.50
    res = estimate_shipping(800)
    assert res['weight_lbs'] == 2.0
    assert res['low'] == 4.50
    assert res['high'] == 5.50

def test_estimate_shipping_very_large():
    # 2000 pages -> 5.0 lbs
    # Extra lbs = 4.0
    # Low = 4.0 + 4.0 * 0.50 = 6.0
    # High = 5.0 + 4.0 * 0.60 = 7.4 -> rounded to 7.50
    res = estimate_shipping(2000)
    assert res['weight_lbs'] == 5.0
    assert res['low'] == 6.0
    assert res['high'] == 7.50
