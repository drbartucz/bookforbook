"""
SMS -> Signal webhook bridge.

aspsms.com is configured to call this app with an HTTP GET request every time
the bound number receives a text message, e.g.

    http://polartechllc.com/text2signal?token=<SECRET>&MessageData=<MessageData>

This app validates the shared secret, then relays the message body into a Signal
group chat via a running signal-cli-rest-api service.

Environment variables (see .env.example):
    WEBHOOK_TOKEN     Shared secret that aspsms must include as ?token=...
    SIGNAL_API_URL    Base URL of the signal-cli-rest-api service
    SIGNAL_NUMBER     The registered Signal bot number in E.164 format (+1...)
    SIGNAL_GROUP_ID   The signal-cli group id ("group.<base64>...")
    MESSAGE_PARAM     Query param name carrying the text (default: MessageData)
    SENDER_PARAM      Optional query param name carrying the sender number
    REQUEST_TIMEOUT   Seconds to wait on the Signal API (default: 10)
    PORT              Provided automatically by Railway
"""

from __future__ import annotations

import hmac
import logging
import os

import requests
from flask import Flask, jsonify, request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("sms-signal-bot")

app = Flask(__name__)


def _env(name: str, default: str | None = None, required: bool = False) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        logger.warning("Environment variable %s is not set", name)
    return value


WEBHOOK_TOKEN = _env("WEBHOOK_TOKEN", required=True)
SIGNAL_API_URL = (_env("SIGNAL_API_URL", required=True) or "").rstrip("/")
SIGNAL_NUMBER = _env("SIGNAL_NUMBER", required=True)
SIGNAL_GROUP_ID = _env("SIGNAL_GROUP_ID", required=True)
MESSAGE_PARAM = _env("MESSAGE_PARAM", "MessageData")
SENDER_PARAM = _env("SENDER_PARAM", "")  # optional; empty disables it
REQUEST_TIMEOUT = float(_env("REQUEST_TIMEOUT", "10"))


def _token_ok(supplied: str | None) -> bool:
    """Constant-time comparison of the supplied token against the secret."""
    if not WEBHOOK_TOKEN or not supplied:
        return False
    return hmac.compare_digest(str(supplied), str(WEBHOOK_TOKEN))


def send_to_signal(message: str) -> tuple[bool, str]:
    """Post a message to the configured Signal group. Returns (ok, detail)."""
    url = f"{SIGNAL_API_URL}/v2/send"
    payload = {
        "message": message,
        "number": SIGNAL_NUMBER,
        "recipients": [SIGNAL_GROUP_ID],
    }
    try:
        resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        return False, f"signal api request failed: {exc}"

    if resp.status_code // 100 == 2:
        return True, "sent"
    return False, f"signal api returned {resp.status_code}: {resp.text[:300]}"


@app.get("/")
def health() -> tuple:
    """Simple health check for Railway / uptime monitors."""
    return jsonify(status="ok", service="sms-signal-bot"), 200


@app.route("/text2signal", methods=["GET", "POST"])
def text2signal():
    # Accept the token and message from query string (GET) or form/JSON (POST).
    source = request.values  # merges args + form
    token = source.get("token") or request.headers.get("X-Webhook-Token")

    if not _token_ok(token):
        logger.warning("Rejected request with bad/missing token from %s", request.remote_addr)
        return jsonify(status="error", detail="unauthorized"), 401

    message = source.get(MESSAGE_PARAM, "").strip()
    if not message:
        return jsonify(status="error", detail=f"missing {MESSAGE_PARAM}"), 400

    # Optionally prefix with the originating number if aspsms is configured to send it.
    if SENDER_PARAM:
        sender = source.get(SENDER_PARAM, "").strip()
        if sender:
            message = f"From {sender}:\n{message}"

    ok, detail = send_to_signal(message)
    if not ok:
        logger.error("Failed to relay to Signal: %s", detail)
        return jsonify(status="error", detail=detail), 502

    logger.info("Relayed %d-char message to Signal group", len(message))
    return jsonify(status="ok"), 200


if __name__ == "__main__":
    # Local dev only; on Railway the app is served by gunicorn (see Procfile).
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
