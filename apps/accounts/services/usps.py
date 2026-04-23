import logging
import time

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

TOKEN_CACHE_KEY = "accounts:usps:oauth_token"


class USPSVerificationError(Exception):
    pass


def _oauth_base_url() -> str:
    return getattr(
        settings,
        "USPS_OAUTH_BASE_URL",
        "https://apis.usps.com/oauth2/v3",
    )


def _addresses_base_url() -> str:
    return getattr(
        settings,
        "USPS_ADDRESSES_BASE_URL",
        "https://apis.usps.com/addresses/v3",
    )


def _get_oauth_token() -> str:
    client_id = getattr(settings, "USPS_CLIENT_ID", "")
    client_secret = getattr(settings, "USPS_CLIENT_SECRET", "")
    scope = getattr(settings, "USPS_OAUTH_SCOPE", "")
    timeout = getattr(settings, "USPS_API_TIMEOUT", 8)

    if not client_id or not client_secret:
        raise USPSVerificationError("USPS address verification is not configured.")

    now = time.time()
    cached_payload = cache.get(TOKEN_CACHE_KEY) or {}
    cached_token = cached_payload.get("access_token")
    cached_expires_at = float(cached_payload.get("expires_at") or 0)
    if cached_token and now < (cached_expires_at - 60):
        return str(cached_token)

    payload: dict[str, str] = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    if scope:
        payload["scope"] = scope

    try:
        resp = requests.post(
            f"{_oauth_base_url()}/token",
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise USPSVerificationError("Unable to authenticate with USPS APIs.") from exc

    try:
        data = resp.json()
    except ValueError as exc:
        raise USPSVerificationError("Invalid USPS OAuth response.") from exc

    access_token = data.get("access_token")
    expires_in = int(data.get("expires_in") or 0)
    if not access_token:
        raise USPSVerificationError(
            "USPS OAuth response did not include an access token."
        )

    expires_at = time.time() + max(expires_in, 300)
    cache.set(
        TOKEN_CACHE_KEY,
        {"access_token": access_token, "expires_at": expires_at},
        timeout=max(expires_in, 300),
    )
    return str(access_token)


def _extract_error_message(resp: requests.Response) -> str:
    try:
        payload = resp.json()
    except ValueError:
        return "USPS address verification failed."

    if isinstance(payload, dict):
        if payload.get("error_description"):
            return str(payload["error_description"])
        if payload.get("message"):
            return str(payload["message"])
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                detail = first.get("detail") or first.get("message")
                if detail:
                    return str(detail)
            if isinstance(first, str):
                return first
    return "USPS address verification failed."


def verify_address_with_usps(
    *, address_line_1: str, address_line_2: str, city: str, state: str, zip_code: str
) -> dict:
    """Validate and normalize an address through USPS Addresses v3 API."""
    timeout = getattr(settings, "USPS_API_TIMEOUT", 8)
    token = _get_oauth_token()

    zip5 = zip_code[:5]
    zip4 = zip_code[6:10] if len(zip_code) > 5 else ""
    params: dict[str, str] = {
        "streetAddress": address_line_1,
        "state": state,
    }
    if address_line_2:
        params["secondaryAddress"] = address_line_2
    if city:
        params["city"] = city
    if zip5:
        params["ZIPCode"] = zip5
    if zip4:
        params["ZIPPlus4"] = zip4

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    try:
        resp = requests.get(
            f"{_addresses_base_url()}/address",
            params=params,
            headers=headers,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise USPSVerificationError(
            "Unable to reach USPS verification service."
        ) from exc

    if resp.status_code == 401:
        # Token may be stale/revoked: clear cache and retry once.
        cache.delete(TOKEN_CACHE_KEY)
        retry_headers = {
            "Authorization": f"Bearer {_get_oauth_token()}",
            "Accept": "application/json",
        }
        try:
            resp = requests.get(
                f"{_addresses_base_url()}/address",
                params=params,
                headers=retry_headers,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise USPSVerificationError(
                "Unable to reach USPS verification service."
            ) from exc

    if resp.status_code in (400, 404):
        raise USPSVerificationError(_extract_error_message(resp))
    if resp.status_code >= 400:
        raise USPSVerificationError(
            "USPS verification service error. Please try again."
        )

    try:
        payload = resp.json()
    except ValueError as exc:
        raise USPSVerificationError("Invalid USPS verification response.") from exc

    address = payload.get("address") if isinstance(payload, dict) else None
    if not isinstance(address, dict):
        raise USPSVerificationError("USPS could not verify this address.")

    verified_line_1 = (
        address.get("streetAddressAbbreviation") or address.get("streetAddress") or ""
    ).strip()
    verified_line_2 = (address.get("secondaryAddress") or "").strip()
    verified_city = (
        address.get("cityAbbreviation") or address.get("city") or ""
    ).strip()
    verified_state = (address.get("state") or "").strip()
    verified_zip5 = (address.get("ZIPCode") or "").strip()
    verified_zip4 = (address.get("ZIPPlus4") or "").strip()

    if not (verified_line_1 and verified_city and verified_state and verified_zip5):
        raise USPSVerificationError("USPS could not verify this address.")

    normalized_zip = (
        f"{verified_zip5}-{verified_zip4}" if verified_zip4 else verified_zip5
    )
    return {
        "address_line_1": verified_line_1,
        "address_line_2": verified_line_2,
        "city": verified_city,
        "state": verified_state,
        "zip_code": normalized_zip,
    }
