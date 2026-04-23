from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from django.test import override_settings

from apps.accounts.services.usps import (
    TOKEN_CACHE_KEY,
    USPSVerificationError,
    _get_oauth_token,
    verify_address_with_usps,
)


@pytest.fixture(autouse=True)
def clear_usps_token_cache():
    cache.delete(TOKEN_CACHE_KEY)
    yield
    cache.delete(TOKEN_CACHE_KEY)


@override_settings(USPS_CLIENT_ID="client-id", USPS_CLIENT_SECRET="client-secret")
def test_get_oauth_token_uses_cache_between_calls():
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "access_token": "token-123",
        "expires_in": 3600,
    }

    with patch(
        "apps.accounts.services.usps.requests.post", return_value=response
    ) as mock_post:
        first = _get_oauth_token()
        second = _get_oauth_token()

    assert first == "token-123"
    assert second == "token-123"
    mock_post.assert_called_once()


@override_settings(USPS_CLIENT_ID="client-id", USPS_CLIENT_SECRET="client-secret")
def test_get_oauth_token_raises_for_malformed_oauth_response():
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.side_effect = ValueError("bad json")

    with patch("apps.accounts.services.usps.requests.post", return_value=response):
        with pytest.raises(USPSVerificationError, match="Invalid USPS OAuth response"):
            _get_oauth_token()


def test_verify_address_retries_once_after_401_and_returns_normalized_address():
    unauthorized = MagicMock()
    unauthorized.status_code = 401

    ok = MagicMock()
    ok.status_code = 200
    ok.json.return_value = {
        "address": {
            "streetAddressAbbreviation": "123 MAIN ST",
            "secondaryAddress": "APT 2",
            "cityAbbreviation": "DENVER",
            "state": "CO",
            "ZIPCode": "80202",
            "ZIPPlus4": "1234",
        }
    }

    with patch(
        "apps.accounts.services.usps._get_oauth_token",
        side_effect=["stale-token", "fresh-token"],
    ) as mock_get_token, patch(
        "apps.accounts.services.usps.requests.get",
        side_effect=[unauthorized, ok],
    ) as mock_get:
        result = verify_address_with_usps(
            address_line_1="123 Main St",
            address_line_2="Apt 2",
            city="Denver",
            state="CO",
            zip_code="80202",
        )

    assert result == {
        "address_line_1": "123 MAIN ST",
        "address_line_2": "APT 2",
        "city": "DENVER",
        "state": "CO",
        "zip_code": "80202-1234",
    }
    assert mock_get_token.call_count == 2
    first_headers = mock_get.call_args_list[0].kwargs["headers"]
    second_headers = mock_get.call_args_list[1].kwargs["headers"]
    assert first_headers["Authorization"] == "Bearer stale-token"
    assert second_headers["Authorization"] == "Bearer fresh-token"


def test_verify_address_raises_for_malformed_usps_payload():
    ok = MagicMock()
    ok.status_code = 200
    ok.json.return_value = {"unexpected": "shape"}

    with patch(
        "apps.accounts.services.usps._get_oauth_token",
        return_value="token-123",
    ), patch("apps.accounts.services.usps.requests.get", return_value=ok):
        with pytest.raises(
            USPSVerificationError, match="could not verify this address"
        ):
            verify_address_with_usps(
                address_line_1="123 Main St",
                address_line_2="",
                city="Denver",
                state="CO",
                zip_code="80202",
            )


def test_verify_address_raises_for_non_json_response():
    ok = MagicMock()
    ok.status_code = 200
    ok.json.side_effect = ValueError("not json")

    with patch(
        "apps.accounts.services.usps._get_oauth_token",
        return_value="token-123",
    ), patch("apps.accounts.services.usps.requests.get", return_value=ok):
        with pytest.raises(
            USPSVerificationError, match="Invalid USPS verification response"
        ):
            verify_address_with_usps(
                address_line_1="123 Main St",
                address_line_2="",
                city="Denver",
                state="CO",
                zip_code="80202",
            )
