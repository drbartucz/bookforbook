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
| Database | PostgreSQL 16 |
| Task queue | Django-Q2 (PostgreSQL broker) |
| Frontend | React 18 (Vite) as PWA |
| ISBN data | Open Library API |
| Auth | JWT (djangorestframework-simplejwt) |
| File storage | S3-compatible |
| Notifications | Email (SendGrid/AWS SES), optional SMS (Twilio) |

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 16 — set up via `setup_postgres.sh` (see below)

### 1. Set up PostgreSQL

Run the setup script once to create a managed PostgreSQL instance:

```bash
sh setup_postgres.sh
```

This creates a PostgreSQL instance at `~/private/postgres1/` running on a Unix socket
(no TCP port — this is normal for this hosting environment).

Load the environment variables it configures:

```bash
source ~/apps/postgres1/home/.bashrc
```

> Add that `source` line to your shell's `~/.bashrc` (or `~/.profile`) so `PGHOST` is set
> automatically on every login.

Verify the instance is running and you can connect:

```bash
psql postgres -c "\conninfo"
```

Create the application database and user:

```bash
# Generate a strong password
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Create the user (replace YOUR_PASSWORD with the generated password)
psql postgres -c "CREATE USER bookforbook WITH PASSWORD 'YOUR_PASSWORD';"

# Create the database owned by that user
psql postgres -c "CREATE DATABASE bookforbook OWNER bookforbook;"

# Grant schema permissions
psql bookforbook -c "GRANT ALL ON SCHEMA public TO bookforbook;"
```

Note your socket directory — you'll need it for `.env`:

```bash
echo $PGHOST
# e.g. /home/yourusername/private/postgres1/run
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```
SECRET_KEY=<generate with: python3 -c "import secrets; print(secrets.token_urlsafe(50))">
DATABASE_URL=postgresql://bookforbook:YOUR_PASSWORD@/bookforbook?host=/home/YOUR_USERNAME/private/postgres1/run
FIELD_ENCRYPTION_KEY=<generate with: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
ALLOWED_HOSTS=yourdomain.com
FRONTEND_URL=https://yourdomain.com
```

Replace `/home/YOUR_USERNAME/private/postgres1/run` with the actual path from `echo $PGHOST`.

### 3. Install dependencies and run migrations

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations accounts
python manage.py migrate
python manage.py createsuperuser
```

### 4. Start the application

#### Development only

```bash
python manage.py runserver
```

Never use this in production — it is single-threaded, not hardened, and not persistent.

#### Production — gunicorn on SureSupport

gunicorn is already in `requirements.txt`. On SureSupport, the control panel manages the reverse proxy and SSL for you — you only need to configure gunicorn and point the webapp at it.

---

##### Step 1 — Create the log directory

```bash
mkdir -p ~/private/logs
```

---

##### Step 2 — Configure gunicorn

`gunicorn.conf.py` is already in the project root. It is pre-configured for this hosting environment:

```python
bind = "0.0.0.0:26386"         # port assigned by SureSupport control panel
workers = 2
timeout = 60
keepalive = 5
accesslog = "/home/bookforbook/private/logs/gunicorn-access.log"
errorlog  = "/home/bookforbook/private/logs/gunicorn-error.log"
loglevel  = "info"
pidfile   = "/tmp/bookforbook.pid"
proc_name = "bookforbook"
```

Replace `bookforbook` in the log paths if your username differs.

---

##### Step 3 — Configure the SureSupport webapp

In the SureSupport control panel, create or edit the webapp for `bookforbook.com` with these settings:

| Setting | Value |
|---------|-------|
| **Start command** | `/home/bookforbook/private/bookforbook/.venv/bin/gunicorn config.wsgi:application -c /home/bookforbook/private/bookforbook/gunicorn.conf.py --chdir /home/bookforbook/private/bookforbook` |
| **Port** | `26386` |
| **Environment variable** | `DJANGO_SETTINGS_MODULE=config.settings.production` |

Replace `bookforbook` in the paths with your actual username if different.

The `--chdir` flag is required so gunicorn finds the project files. The full path to the gunicorn binary is required so it uses the virtualenv Python with all packages installed.

The `.env` file is loaded automatically by `python-decouple` — you do not need to duplicate all variables in the control panel. Only `DJANGO_SETTINGS_MODULE` needs to be set there.

---

##### Step 4 — Collect static files

Django does not serve static files itself in production. Run this once (and again after any code update that changes static files):

```bash
cd ~/private/bookforbook
source .venv/bin/activate
python manage.py collectstatic --noinput
```

This copies everything to `staticfiles/`. Static files are served by **WhiteNoise** directly from the gunicorn process — no separate web server step needed. WhiteNoise also compresses files and adds cache-busting hashes to filenames automatically.

> **Important:** Run `collectstatic` before the first startup and after any code update that adds or changes static files (CSS, JS, images). If you forget, the admin panel will load without styles.

---

##### Step 5 — Start the webapp

Start (or restart) the webapp from the SureSupport control panel. Check the error log if it doesn't come up:

```bash
tail -f ~/private/logs/gunicorn-error.log
```

---

##### Reloading after code updates

After `git pull origin main` and `python manage.py migrate`, reload gunicorn without dropping connections:

```bash
kill -HUP $(cat /tmp/bookforbook.pid)
```

Or restart the webapp from the SureSupport control panel (causes a few seconds of downtime).

---

##### If the web server is not managed by SureSupport

On a VPS or server where you have full access, you need to configure the reverse proxy yourself. Check which web server is running:

```bash
ps aux | grep -E 'nginx|apache|httpd' | grep -v grep
```

###### nginx config

```nginx
server {
    listen 80;
    server_name bookforbook.com www.bookforbook.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name bookforbook.com www.bookforbook.com;

    ssl_certificate     /etc/letsencrypt/live/bookforbook.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bookforbook.com/privkey.pem;

    location /static/ {
        alias /home/bookforbook/private/bookforbook/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:26386;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/bookforbook /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

###### Apache config

```apache
<VirtualHost *:80>
    ServerName bookforbook.com
    ServerAlias www.bookforbook.com
    Redirect permanent / https://bookforbook.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName bookforbook.com
    ServerAlias www.bookforbook.com

    SSLEngine on
    SSLCertificateFile    /etc/letsencrypt/live/bookforbook.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/bookforbook.com/privkey.pem

    ProxyPreserveHost On
    ProxyPass        /static/ !
    Alias            /static/ /home/bookforbook/private/bookforbook/staticfiles/
    ProxyPass / http://127.0.0.1:26386/
    ProxyPassReverse / http://127.0.0.1:26386/
    RequestHeader set X-Forwarded-Proto "https"
</VirtualHost>
```

```bash
sudo a2enmod proxy proxy_http headers ssl rewrite
sudo a2ensite bookforbook.conf
sudo apache2ctl configtest && sudo systemctl reload apache2
```

SSL certificate (both web servers):

```bash
sudo certbot --nginx -d bookforbook.com -d www.bookforbook.com
# or: sudo certbot --apache -d bookforbook.com -d www.bookforbook.com
```

---

##### Periodic tasks are run via cron (no background worker needed)

See the crontab entries in `SUPERUSER.md` under **Cron Schedule Reference**.

### 5. Frontend

The frontend is a React PWA built with Vite. It talks to the Django API over HTTPS and is deployed separately on **Cloudflare Pages** (free tier, global CDN).

#### Development

```bash
cd frontend
npm install
npm run dev
```

The dev server proxies `/api` to `http://localhost:8000` automatically — no env vars needed.

---

#### Production — Cloudflare Pages

Cloudflare Pages builds and hosts the React app. The Django API runs separately at `api.bookforbook.com`.

> **Cloudflare Pages vs Cloudflare Workers — use Pages.** These are two different products. Pages is for hosting static sites and SPAs built from a git repo. Workers is a serverless compute platform. Using Workers by mistake will cause the build to fail with wrangler errors. Always use the **Pages** flow described below.

##### Step 1 — Add the API subdomain on SureSupport

Adding `api.bookforbook.com` routes API traffic to the same gunicorn webapp as `bookforbook.com`. Django already accepts this hostname in `ALLOWED_HOSTS`.

In the SureSupport control panel:

1. Add a subdomain `api.bookforbook.com`. SureSupport will ask for a document root folder — set it to `www/www` or whatever the default is. **This folder is never used** since all requests are forwarded to gunicorn; the value doesn't matter.
2. Add `api.bookforbook.com` as an additional hostname on your existing gunicorn webapp.

##### Step 2 — Allow the frontend domain in Django CORS

In `.env` on the server, set:

```
CORS_ALLOWED_ORIGINS=https://bookforbook.com,https://www.bookforbook.com
```

Reload gunicorn after saving:

```bash
kill -HUP $(cat /tmp/bookforbook.pid)
```

##### Step 3 — Deploy to Cloudflare Pages

1. Log in to [dash.cloudflare.com](https://dash.cloudflare.com) → **Workers & Pages** → **Create** → **Pages** → **Connect to Git**

   > Do not choose **Workers** — that is a different product.

2. Select the `bookforbook` repository
3. Configure the build:

   | Setting | Value |
   |---------|-------|
   | **Framework preset** | None |
   | **Build command** | `npm run build` |
   | **Build output directory** | `dist` |
   | **Root directory** | `frontend` |

4. Add an environment variable under **Settings → Environment variables → Production**:

   | Variable | Value |
   |----------|-------|
   | `VITE_API_URL` | `https://api.bookforbook.com` |

5. Click **Save and Deploy**. Cloudflare builds the app and deploys it globally in ~2 minutes.

##### Step 4 — DNS configuration

**Overview — what points where:**

| Hostname | Destination | Why |
|----------|-------------|-----|
| `bookforbook.com` | Cloudflare Pages | Serves the React frontend |
| `www.bookforbook.com` | Cloudflare Pages | Serves the React frontend |
| `api.bookforbook.com` | SureSupport server | Serves the Django API |

Cloudflare manages all three DNS records. `bookforbook.com` and `www` are proxied through Cloudflare (CDN + DDoS protection). `api` bypasses Cloudflare's proxy and goes direct to SureSupport — this is required so Django sees real user IPs for logging and rate limiting.

---

**4a — Find your SureSupport server IP**

You need this before starting. SSH into the server and run:

```bash
curl -s ifconfig.me
```

Note the IP address — you'll enter it as the `api` DNS record shortly.

---

**4b — Add your domain to Cloudflare**

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
| A | `api` | *(your SureSupport server IP from step 4a)* | **DNS only** (grey cloud) |

To set proxy status when creating a record: there is a toggle labelled **Proxy status** — orange cloud means proxied, grey cloud means DNS only. Make sure `api` is grey.

> The `@` symbol means the root domain (`bookforbook.com` itself). Some DNS interfaces show it as `@`, some show the full domain name.

---

**4e — Add custom domains to Cloudflare Pages**

1. In Cloudflare dashboard → **Workers & Pages** → your Pages project → **Custom domains**
2. Click **Set up a custom domain**
3. Enter `bookforbook.com` → click **Continue** → **Activate domain**
4. Repeat for `www.bookforbook.com`

Because Cloudflare manages your DNS, it will verify and activate each domain automatically within a few minutes. SSL certificates are provisioned at the same time — no separate step needed.

---

**4f — Verify everything is working**

```bash
# Frontend should load
curl -I https://bookforbook.com
# Expected: HTTP 200

# API should respond
curl -I https://api.bookforbook.com/api/v1/browse/
# Expected: HTTP 200, not a certificate error
```

##### Deploying updates

Every push to the main branch triggers an automatic rebuild and deploy — no manual steps needed.

To rebuild manually: Cloudflare Pages dashboard → **Deployments** → **Retry deployment**.

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
- **Exchange rings** — the system detects cycles of 3–5 users who can all trade with each other
- **Inactivity** — books are auto-hidden after 3 months of inactivity and restored on next login

## Docs

See [`docs/bookswap-architecture.md`](docs/bookswap-architecture.md) for the full architecture specification and 8-phase build roadmap.

## License

MIT
