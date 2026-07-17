# SMS → Signal webhook bridge

A tiny Python (Flask) web service that receives an HTTP GET from
[aspsms.com](https://www.aspsms.com/) whenever a bound number gets a text
message, and relays the message body into a **Signal group chat**.

```
 ┌──────────┐   incoming SMS    ┌───────────┐   HTTP GET    ┌──────────────────┐
 │  sender  │ ────────────────▶ │  aspsms   │ ────────────▶ │  this Flask app  │
 └──────────┘                   └───────────┘               │ (polartechllc)   │
                                                             └────────┬─────────┘
                                                        POST /v2/send │
                                                                      ▼
                                                        ┌──────────────────────────┐
                                                        │  signal-cli-rest-api      │
                                                        │  (registered bot number)  │
                                                        └────────────┬──────────────┘
                                                                     ▼
                                                             Signal group chat
```

The webhook aspsms calls looks like:

```
http://polartechllc.com/text2signal?token=<SECRET>&MessageData=<MessageData>
```

- `token` — a shared secret. Requests without the correct token are rejected
  with `401`, so a random passer-by cannot post into your Signal group.
- `MessageData` — the text of the SMS (aspsms fills this in via its placeholder).

---

## What you deploy

You run **two services on Railway**:

1. **`signal-cli-rest-api`** — the Signal backend (a prebuilt Docker image). It
   owns the registered bot phone number and exposes an HTTP API for sending
   messages.
2. **This app** (`sms-signal-bot`) — the webhook that aspsms hits, which calls
   service #1 to post into the group.

---

## Prerequisites

- A [Railway](https://railway.app/) account and project.
- The `polartechllc.com` domain, ready to point at the webhook service.
- A **dedicated phone number already registered with Signal** for the bot. (If
  yours is not registered yet, see [Appendix: registering a Signal number](#appendix-registering-a-signal-number-if-you-ever-need-it).)
- The bot number must be a **member of the target Signal group** (add it from
  your normal Signal app, or create the group with it).

---

## Step 1 — Deploy `signal-cli-rest-api` on Railway

1. In your Railway project: **New → Empty Service** (or "Deploy a Docker Image").
2. Set the Docker image to:
   ```
   bbernhard/signal-cli-rest-api:latest
   ```
3. Add a **Variable**:
   ```
   MODE=native
   ```
   (`native` mode is required for group messaging and JSON-RPC; it is the
   recommended mode.)
4. Add a **Volume** mounted at `/home/.local/share/signal-cli` so the
   registration/session survives restarts. **Without a persistent volume you
   will have to re-register after every deploy.**
5. This service does **not** need a public domain. Note its **private
   networking** hostname, e.g. `signal-cli-rest-api.railway.internal`, and the
   internal port (default `8080`).

> The bot number should already be registered. If you registered it elsewhere,
> the linked/registered session lives in that mounted volume — see the appendix.

### Find your group id

With the service running, list the groups the bot is in (run from your machine,
using the service's **public** URL temporarily, or from Railway's shell):

```bash
curl "http://<signal-cli-rest-api-host>:8080/v1/groups/+15551234567"
```

Copy the `"id"` field of the target group — it looks like `group.aBcD...==`.
That value is your `SIGNAL_GROUP_ID`.

---

## Step 2 — Deploy this app on Railway

1. Push this repository to GitHub (this app lives in the `sms-signal-bot/`
   directory).
2. In Railway: **New → GitHub Repo**, pick the repo.
3. In the service **Settings → Root Directory**, set:
   ```
   sms-signal-bot
   ```
   so Railway builds only this folder. Railway (Nixpacks) auto-detects Python
   from `requirements.txt` and starts the app via the `Procfile` /
   `railway.json` start command (`gunicorn app:app ...`).
4. Add the environment variables (see [Configuration](#configuration) below).
5. Under **Settings → Networking**, add a public domain and point
   **`polartechllc.com`** at it:
   - Add the custom domain `polartechllc.com` in Railway.
   - Create the DNS record Railway shows you (a `CNAME`, or an `A`/`ALIAS` at the
     apex per your DNS provider) at your registrar.
   - Wait for the domain to go green in Railway.

> aspsms calls the URL over **HTTP** (`http://polartechllc.com/...`). Railway
> serves HTTPS on custom domains and will happily accept the HTTP request and
> redirect/serve it. If aspsms does **not** follow redirects, use the URL exactly
> as your endpoint resolves — Railway terminates TLS, so `https://` also works if
> aspsms supports it.

---

## Configuration

Set these as Railway **Variables** on the `sms-signal-bot` service (see
`.env.example`):

| Variable          | Required | Example                                             | Notes |
|-------------------|----------|-----------------------------------------------------|-------|
| `WEBHOOK_TOKEN`   | ✅       | `k3y-9f2...` (long random string)                   | Shared secret aspsms must send as `?token=`. |
| `SIGNAL_API_URL`  | ✅       | `http://signal-cli-rest-api.railway.internal:8080`  | Private URL of service #1. |
| `SIGNAL_NUMBER`   | ✅       | `+15551234567`                                       | Registered bot number, E.164. |
| `SIGNAL_GROUP_ID` | ✅       | `group.aBcD...==`                                    | From `GET /v1/groups/<number>`. |
| `MESSAGE_PARAM`   | ➖       | `MessageData`                                        | Query param carrying the text. Default `MessageData`. |
| `SENDER_PARAM`    | ➖       | `Sender`                                             | If set and present, message is prefixed with the sender. Blank = off. |
| `REQUEST_TIMEOUT` | ➖       | `10`                                                 | Seconds to wait on the Signal API. |
| `PORT`            | auto     | —                                                    | Injected by Railway. Do not set manually. |

Generate a strong token:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Step 3 — Configure aspsms

In your aspsms account, set the **inbound / originator forwarding URL** for the
number to (URL-encode the token; aspsms substitutes its own `<MessageData>`
placeholder):

```
http://polartechllc.com/text2signal?token=YOUR_WEBHOOK_TOKEN&MessageData=<MessageData>
```

aspsms uses angle-bracket placeholders. The exact placeholder name for the
message body in your aspsms configuration is typically `<MessageData>` (or
`<Text>` depending on the product) — match it to whatever aspsms substitutes,
and keep the query-string key equal to `MESSAGE_PARAM` (default `MessageData`).

If aspsms can also send the originating number, add it and set `SENDER_PARAM`
accordingly, e.g.:

```
...&MessageData=<MessageData>&Sender=<Originator>
```

then set `SENDER_PARAM=Sender`.

---

## Endpoints

| Method  | Path           | Purpose |
|---------|----------------|---------|
| `GET`   | `/`            | Health check (`{"status":"ok"}`). Used by Railway. |
| `GET`/`POST` | `/text2signal` | Receives the SMS relay. Requires valid `token`. |

Auth: the token may be sent as `?token=...` **or** as an `X-Webhook-Token`
header. It is compared in constant time.

---

## Test it

Locally:

```bash
cd sms-signal-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # then edit values
export $(grep -v '^#' .env | xargs)   # load env vars
python app.py           # serves on http://localhost:8080
```

In another terminal:

```bash
# Health
curl http://localhost:8080/

# Simulate an aspsms hit (should post into your Signal group)
curl "http://localhost:8080/text2signal?token=YOUR_WEBHOOK_TOKEN&MessageData=hello%20from%20sms"

# Wrong token -> 401
curl -i "http://localhost:8080/text2signal?token=nope&MessageData=hi"
```

Once deployed, repeat against `http://polartechllc.com/text2signal?...` and send
a real text to the aspsms number.

---

## Troubleshooting

- **401 unauthorized** — the `token` query param does not match `WEBHOOK_TOKEN`.
- **400 missing MessageData** — aspsms sent a different param name; align
  `MESSAGE_PARAM` with the aspsms placeholder key.
- **502 signal api returned ...** — the `signal-cli-rest-api` service is
  unreachable, the number is not registered, the bot is not in the group, or the
  group id is wrong. Check that service's logs and re-run
  `GET /v1/groups/<number>`.
- **Messages never arrive but return 200** — verify `SIGNAL_GROUP_ID` and that
  the bot number is a member of that group.
- **Registration lost after deploy** — you forgot the persistent volume on the
  `signal-cli-rest-api` service.

---

## Appendix: registering a Signal number (if you ever need it)

Your bot number is expected to be registered already. If you need to (re)register:

1. Use the `signal-cli-rest-api` service in `native` mode with the volume
   mounted.
2. Get a captcha token from <https://signalcaptchas.org/registration/generate.html>
   (copy the `signalcaptcha://...` value).
3. Register:
   ```bash
   curl -X POST "http://<host>:8080/v1/register/+15551234567" \
        -H "Content-Type: application/json" \
        -d '{"captcha":"signalcaptcha://...", "use_voice": false}'
   ```
4. Verify with the SMS/voice code you receive:
   ```bash
   curl -X POST "http://<host>:8080/v1/register/+15551234567/verify/123456"
   ```
5. Create or join the target group, then fetch its id with
   `GET /v1/groups/+15551234567`.

See the [signal-cli-rest-api docs](https://github.com/bbernhard/signal-cli-rest-api)
for full details.
