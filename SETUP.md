# BookForBook

A book bartering platform where users in the continental USA trade books 1-for-1 — no money changes hands.

## How It Works

1. List books you want to give away (by ISBN) with a condition rating
2. Add books to your want list
3. The system automatically detects mutual matches and exchange rings (up to 5 people)
4. All parties confirm the trade; shipping addresses are revealed only then
5. Ship your book, mark it received, and leave a rating

Verified libraries and bookstores can receive book donations.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.x + Django REST Framework |
| Database | PostgreSQL 16 (Railway managed) |
| Task queue | Django-Q2 (PostgreSQL broker) |
| Frontend | React 18 (Vite) as PWA on Cloudflare Pages |
| ISBN data | Open Library API |
| Auth | JWT (djangorestframework-simplejwt) |
| Email | Proton Mail (custom domain + SMTP submission) |
| Hosting | Railway (API + worker), Cloudflare Pages (frontend) |

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 16 (for local development)

### 1. Set up PostgreSQL (local dev)

```bash
# macOS
brew install postgresql@16 && brew services start postgresql@16

# Ubuntu/Debian
sudo apt install postgresql-16 && sudo service postgresql start
```

Create the database user and database:

```bash
psql postgres -c "CREATE USER bookforbook WITH PASSWORD 'bookforbook';"
psql postgres -c "CREATE DATABASE bookforbook OWNER bookforbook;"
psql bookforbook -c "GRANT ALL ON SCHEMA public TO bookforbook;"
```

> If `psql postgres` fails with "role does not exist", your PostgreSQL superuser is your macOS username. Use:
> ```bash
> psql -U $(whoami) postgres -c "CREATE USER bookforbook WITH PASSWORD 'bookforbook';"
> psql -U $(whoami) postgres -c "CREATE DATABASE bookforbook OWNER bookforbook;"
> psql -U $(whoami) bookforbook -c "GRANT ALL ON SCHEMA public TO bookforbook;"
> ```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```
SECRET_KEY=<generate with: python3 -c "import secrets; print(secrets.token_urlsafe(50))">
DATABASE_URL=postgresql://bookforbook:bookforbook@localhost:5432/bookforbook
FIELD_ENCRYPTION_KEY=<generate with: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
```

### 3. Install dependencies, migrate, and create superuser

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
```

> **Python version:** Use Python 3.12 to match Railway. If you have multiple versions installed: `python3.12 -m venv .venv`
>
> **Order matters:** `migrate` must run before `runserver`. `createsuperuser` is needed to access `/admin/`.
>
> **No `makemigrations` needed on a fresh checkout** — migration files are committed to the repo. Only run `makemigrations` when you change a model.

### 4. Start the application (local dev)

```bash
# Terminal 1 — Django dev server
python manage.py runserver

# Terminal 2 — Django-Q2 task worker (optional locally, required in production)
python manage.py qcluster
```

### 5. Frontend (local dev)

```bash
cd frontend
npm install
npm run dev
```

The dev server proxies `/api` to `http://localhost:8000` automatically.

---

## Production Deployment

BookForBook runs on two services:

| Service | Platform | Purpose |
|---------|----------|---------|
| API + worker | Railway | Django API (gunicorn) + Django-Q2 task worker |
| Frontend | Cloudflare Pages | React PWA (static build, global CDN) |

### Email — Proton Mail Setup

Proton Mail handles both inbound email (`info@bookforbook.com` inbox) and outbound transactional email from Django (verification emails, password resets, notifications) via Proton's SMTP submission feature.

#### Step 1 — Create a Proton Mail account and add the custom domain

1. Sign up or log in at [proton.me](https://proton.me) (a paid plan is required for custom domains and SMTP submission)
2. Go to **Settings** > **All settings** > **Domain names** > **Add domain**
3. Enter `bookforbook.com` and follow the verification steps
4. Proton will give you DNS records to add — add them all in Cloudflare DNS:

   | Type | Purpose | Proxy status |
   |------|---------|--------------|
   | TXT | Domain ownership verification | DNS only |
   | MX | Inbound mail delivery | DNS only |
   | TXT | SPF | DNS only |
   | CNAME | DKIM (×3) | DNS only |
   | TXT | DMARC | DNS only |

   > All email DNS records must be **DNS only** (grey cloud) — never proxied.

   > **MX records conflict warning:** Adding Proton's MX records takes over all inbound mail for `bookforbook.com`. Remove any existing MX records first. Do not add Cloudflare Email Routing MX records alongside Proton's.

5. Once Proton verifies the domain, create a mailbox address — e.g. `info@bookforbook.com`

#### Step 2 — Generate an SMTP token for Django

Proton Mail uses a dedicated SMTP token (not your login password) to authenticate outbound sending from third-party apps.

1. Go to **Settings** > **All settings** > **Email** > **SMTP submission**
2. Enable SMTP submission if not already enabled
3. Click **Generate token**
4. Note the token — **you cannot view it again after closing the dialog**

The SMTP settings for Django are:

| Setting | Value |
|---------|-------|
| Host | `smtp.protonmail.ch` |
| Port | `587` |
| Username | Your Proton Mail address (e.g. `info@bookforbook.com`) |
| Password | The SMTP token generated above |
| TLS | STARTTLS (enabled) |

#### Step 3 — Set environment variables in Railway

| Variable | Value |
|----------|-------|
| `EMAIL_HOST` | `smtp.protonmail.ch` |
| `EMAIL_PORT` | `587` |
| `EMAIL_HOST_USER` | `info@bookforbook.com` |
| `EMAIL_HOST_PASSWORD` | *(your Proton SMTP token)* |
| `EMAIL_USE_TLS` | `True` |
| `DEFAULT_FROM_EMAIL` | `noreply@bookforbook.com` |

> Note: `DEFAULT_FROM_EMAIL` can be any address on your verified domain. If you want to send as `noreply@bookforbook.com`, add that as an additional address in Proton Mail settings.

### Railway — API Deployment

#### Step 1 — Create a Railway project

1. Sign up at [railway.com](https://railway.com) and connect your GitHub account
2. Click **New Project** > **Deploy from GitHub repo**
3. Select the `bookforbook` repository

Railway detects the `Procfile` and creates a service automatically. The `Procfile` defines two process types:

```
web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
worker: python manage.py qcluster
```

Railway will initially deploy only the `web` service. You need to add the worker separately.

#### Step 2 — Add a PostgreSQL database

1. In your Railway project, click **New** > **Database** > **PostgreSQL**
2. Railway automatically sets the `DATABASE_URL` environment variable on all services in the project

#### Step 3 — Add the worker service

1. In your Railway project, click **New** > **Service** > select the same GitHub repo
2. Go to the new service's **Settings** > **Deploy** section
3. Set the **Start command** to: `python manage.py qcluster`
4. The worker shares the same environment variables as the web service (they're project-level)

#### Step 4 — Set environment variables

In Railway, go to your **web service** > **Variables** and add:

| Variable | Value |
|----------|-------|
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` |
| `SECRET_KEY` | *(generate a secure key)* |
| `FIELD_ENCRYPTION_KEY` | *(generate with Fernet)* |
| `ALLOWED_HOSTS` | `bookforbook.com,www.bookforbook.com,api.bookforbook.com` |
| `CORS_ALLOWED_ORIGINS` | `https://bookforbook.com,https://www.bookforbook.com` |
| `FRONTEND_URL` | `https://bookforbook.com` |
| `EMAIL_HOST` | `smtp.protonmail.ch` |
| `EMAIL_PORT` | `587` |
| `EMAIL_HOST_USER` | `info@bookforbook.com` |
| `EMAIL_HOST_PASSWORD` | *(your Proton SMTP token)* |
| `EMAIL_USE_TLS` | `True` |
| `DEFAULT_FROM_EMAIL` | `noreply@bookforbook.com` |

> `DATABASE_URL` is set automatically by Railway when you add PostgreSQL. Do not set it manually.

> **Shared variables are not applied automatically.** After setting variables on the web service, go to the **worker service → Variables** and add the same variables manually. Both services need `SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `DATABASE_URL`, `DJANGO_SETTINGS_MODULE`, and any email/AWS variables.

#### Step 5 — Run initial setup

Go to your **PostgreSQL service** in Railway → **"Connect"** tab → copy the **Public URL** (starts with `postgresql://postgres:...@roundhouse.proxy.rlwy.net:...`).

Then run from your local machine using that public URL:

```bash
DATABASE_URL="<paste-public-url>" python manage.py migrate
DATABASE_URL="<paste-public-url>" python manage.py createsuperuser
```

> `migrate` creates the database tables. `createsuperuser` gives you access to `/admin/`.
>
> `collectstatic` runs automatically on every Railway deploy via `railway.toml` — you do not need to run it manually.
>
> **Why the public URL?** The internal URL (`postgres.railway.internal`) is only reachable from inside Railway's network. The public URL works from your Mac.

#### Step 6 — Add a custom domain

1. In your web service's **Settings** > **Networking** > **Public Networking**
2. Click **Generate Domain** to get a `*.up.railway.app` URL (for testing)
3. Click **Add Custom Domain** and enter `api.bookforbook.com`
4. Railway shows a CNAME target — add this in Cloudflare DNS:

| Type | Name | Content | Proxy status |
|------|------|---------|--------------|
| CNAME | `api` | *(Railway CNAME target)* | **DNS only** (grey cloud) |

> Use **DNS only** (grey cloud) so Railway can provision its own TLS certificate. If you proxy through Cloudflare (orange cloud), Railway cannot verify domain ownership.

#### Step 7 — Verify

```bash
# API should respond
curl https://api.bookforbook.com/api/v1/browse/available/

# Check the Railway-assigned domain too
curl https://your-app.up.railway.app/api/v1/browse/available/
```

#### Deploying updates

Every push to the main branch triggers an automatic build and deploy on Railway. No manual steps needed.

To deploy manually: Railway dashboard > your service > **Deploy** > **Trigger Deploy**.

### Cloudflare Pages — Frontend Deployment

The frontend is a React PWA built with Vite. It is deployed separately on Cloudflare Pages (free tier).

#### Step 1 — Deploy to Cloudflare Pages

1. Log in to [dash.cloudflare.com](https://dash.cloudflare.com) > **Workers & Pages** > **Create** > **Pages** > **Connect to Git**

   > Do not choose **Workers** — that is a different product and will fail.

2. Select the `bookforbook` repository
3. Configure the build:

   | Setting | Value |
   |---------|-------|
   | **Framework preset** | None |
   | **Build command** | `npm run build` |
   | **Build output directory** | `dist` |
   | **Root directory** | `frontend` |

4. Add an environment variable under **Settings > Environment variables > Production**:

   | Variable | Value |
   |----------|-------|
   | `VITE_API_URL` | `https://api.bookforbook.com/api/v1` |

   > Note the `/api/v1` suffix — the frontend appends paths like `/browse/` directly to this value.

5. Click **Save and Deploy**

#### Step 2 — DNS configuration

**Overview — what points where:**

| Hostname | Destination | Why |
|----------|-------------|-----|
| `bookforbook.com` | Cloudflare Pages | React frontend |
| `www.bookforbook.com` | Cloudflare Pages | React frontend |
| `api.bookforbook.com` | Railway | Django API |

##### Add your domain to Cloudflare

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) and log in (create a free account if needed)
2. Click **Add a domain**
3. Enter `bookforbook.com` and click **Continue**
4. Select the **Free** plan and click **Continue**
5. Cloudflare scans your existing DNS records and shows them. Review the list — it may have pre-populated some records from your current ICDSoft DNS. You can leave these for now; you'll adjust them in the next step.
6. Click **Continue to nameservers**
7. Cloudflare shows you **two nameserver addresses** — they look like:
   ```
   aida.ns.cloudflare.com
   bert.ns.cloudflare.com
   ```
   (yours will have different names — copy the exact values shown on screen)

---

**4c — Update nameservers at ICDSoft**

1. Log in to the **ICDSoft Account Panel** (not the hosting Control Panel — this is the billing/domain management panel at account.icdsoft.com)
2. Go to **Hosting Resources** → **Domains**
3. Click on **bookforbook.com**
4. Find the **Nameservers** section
5. Replace the existing nameservers with the two Cloudflare nameservers from the previous step
6. Save

Nameserver propagation typically takes 5–30 minutes but can take up to 24 hours. Cloudflare will email you when your domain is active. You can also check status in the Cloudflare dashboard — the domain will show **Active** when propagation is complete.

---

**4d — Create DNS records in Cloudflare**

Once the domain is active, go to Cloudflare dashboard → **bookforbook.com** → **DNS** → **Records**.

Cloudflare auto-imports your existing DNS records when you add the domain. You must delete the conflicting ones before adding the new records — Cloudflare will not let you add a CNAME if an A or AAAA record with the same name already exists.

Delete any existing **A**, **AAAA**, or **CNAME** records named `@` or `www`. Do **not** delete MX or TXT records — those handle email and domain verification.

Then create:

| Type | Name | Content | Proxy status |
|------|------|---------|--------------|
| CNAME | `@` | `bookforbook.pages.dev` | **Proxied** (orange cloud) |
| CNAME | `www` | `bookforbook.pages.dev` | **Proxied** (orange cloud) |
| CNAME | `api` | *(Railway CNAME target)* | **DNS only** (grey cloud) |

##### Add custom domains to Cloudflare Pages

1. In Cloudflare > **Workers & Pages** > your Pages project > **Custom domains**
2. Add `bookforbook.com` and `www.bookforbook.com`

##### Verify

```bash
# Frontend
curl -I https://bookforbook.com
# Expected: HTTP 200

# API
curl https://api.bookforbook.com/api/v1/browse/available/
# Expected: JSON response
```

#### Deploying updates

Every push to the main branch triggers an automatic rebuild. To rebuild manually: Cloudflare Pages dashboard > **Deployments** > **Retry deployment**.

### Seed development data

```bash
python scripts/seed_data.py
```

## API

All endpoints live under `/api/v1/`. JWT auth is required except for browse/search and public profiles.

| Prefix | Description |
|---|---|
| `auth/` | Register, verify email, login, refresh token, password reset |
| `users/` | Profile, ratings, GDPR export/delete |
| `books/` | ISBN lookup, search |
| `my-books/` | Have-list management |
| `wishlist/` | Want-list management |
| `matches/` | Auto-detected matches; accept/decline |
| `proposals/` | User-initiated trade proposals |
| `trades/` | Shipment tracking, messaging, ratings |
| `donations/` | Institutional donation workflow |
| `institutions/` | Library/bookstore directory |
| `browse/` | Public book discovery, shipping estimates |

## Project Structure

```
bookforbook/
├── config/                  # Django project settings, URLs
├── apps/
│   ├── accounts/            # User model, auth, profiles
│   ├── books/               # Book cache, ISBN lookup, Open Library client
│   ├── inventory/           # Have-list (UserBook) and want-list (WishlistItem)
│   ├── matching/            # Direct match + exchange ring detection
│   ├── trading/             # Proposals, trades, shipment tracking
│   ├── donations/           # Institutional donation workflow
│   ├── ratings/             # 1-5 star ratings with rolling average
│   ├── notifications/       # Email/in-app notifications via Django-Q2
│   └── messaging/           # Structured trade messages
├── frontend/                # React PWA (Vite)
├── scripts/                 # Dev utilities (seed data)
└── docs/                    # Architecture specification
```

## Running Tests

```bash
pytest
```

## Key Business Rules

- **1-for-1 only** — every trade is exactly one book in each direction
- **Continental USA only** — shipping addresses validated to continental US states
- **Match capacity** — new users get 1 active match slot; grows to 10 with trading history
- **Address privacy** — shipping addresses are encrypted at rest and revealed only to confirmed trade partners
- **Exchange rings** — the system detects cycles of 3-5 users who can all trade with each other
- **Inactivity** — books are auto-hidden after 3 months of inactivity and restored on next login

## Docs

See [`docs/bookswap-architecture.md`](docs/bookswap-architecture.md) for the full architecture specification and 8-phase build roadmap.

## License

MIT
