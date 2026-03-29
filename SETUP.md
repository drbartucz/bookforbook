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

#### Production — gunicorn

gunicorn is already in `requirements.txt`. It serves Django over HTTP and handles multiple concurrent requests. A reverse proxy (nginx or Apache) sits in front of it, handles SSL, and forwards requests to gunicorn.

---

##### Step 1 — Find your port and web server

First, pick an unused port for gunicorn to listen on. Any port above 1024 that isn't already in use is fine — `8000` is a common choice.

Check whether nginx or Apache is running:

```bash
nginx -v 2>/dev/null && echo "nginx is installed"
apache2 -v 2>/dev/null && echo "apache2 is installed"
httpd -v 2>/dev/null && echo "httpd (Apache) is installed"
```

Or check running processes:

```bash
ps aux | grep -E 'nginx|apache|httpd' | grep -v grep
```

Use whichever is running. Most SureSupport servers run Apache. If neither returns output, contact SureSupport support to confirm.

---

##### Step 2 — Create the gunicorn config

```bash
mkdir -p ~/logs
```

Edit `~/private/bookforbook/gunicorn.conf.py`:

```python
bind = "127.0.0.1:8000"        # listen on localhost only — nginx/Apache proxies to this
workers = 2
timeout = 60
accesslog = "/home/bookforbook/logs/gunicorn-access.log"
errorlog  = "/home/bookforbook/logs/gunicorn-error.log"
loglevel  = "info"
pidfile   = "/tmp/bookforbook.pid"
proc_name = "bookforbook"
```

Replace `bookforbook` in log paths with your actual username.

---

##### Step 3 — Start gunicorn in a screen session

```bash
screen -S bookforbook
cd ~/private/bookforbook
source .venv/bin/activate
gunicorn config.wsgi:application -c gunicorn.conf.py
```

Detach without stopping: press `Ctrl+A` then `D`.

Reattach later: `screen -r bookforbook`

---

##### Step 4 — Configure the reverse proxy

The reverse proxy receives requests on port 80/443 and forwards them to gunicorn on port 8000.

###### If nginx is running

Find where your site config lives:

```bash
ls /etc/nginx/sites-available/
ls /etc/nginx/conf.d/
```

Create or edit the config for your domain. If you have write access:

```bash
sudo nano /etc/nginx/sites-available/bookforbook
```

```nginx
server {
    listen 80;
    server_name bookforbook.com www.bookforbook.com;

    # Redirect all HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name bookforbook.com www.bookforbook.com;

    ssl_certificate     /etc/letsencrypt/live/bookforbook.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/bookforbook.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /home/bookforbook/private/bookforbook/staticfiles/;
    }
}
```

Enable the site and reload:

```bash
sudo ln -s /etc/nginx/sites-available/bookforbook /etc/nginx/sites-enabled/
sudo nginx -t        # test config — must say "ok"
sudo systemctl reload nginx
```

###### If Apache is running

Find your virtualhost config directory:

```bash
ls /etc/apache2/sites-available/
ls /etc/httpd/conf.d/
```

Create a config file:

```bash
sudo nano /etc/apache2/sites-available/bookforbook.conf
```

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
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/

    RequestHeader set X-Forwarded-Proto "https"
</VirtualHost>
```

Enable required modules and the site, then reload:

```bash
sudo a2enmod proxy proxy_http headers ssl rewrite
sudo a2ensite bookforbook.conf
sudo apache2ctl configtest   # must say "Syntax OK"
sudo systemctl reload apache2
```

###### If you don't have sudo access (shared hosting)

SureSupport may provide a control panel option to configure a reverse proxy or "Python app" for your domain. Look for:

- **"Proxy"** or **"Reverse proxy"** settings
- **"Python app"** or **"WSGI app"** configuration
- **"Custom port"** or **"App port"** under your domain settings

Point it at `127.0.0.1:8000`. If none of these options exist, contact SureSupport support and tell them you need HTTP requests for `bookforbook.com` proxied to `127.0.0.1:8000`.

---

##### Step 5 — SSL certificate

If Let's Encrypt (`certbot`) is available:

```bash
sudo certbot --nginx -d bookforbook.com -d www.bookforbook.com
# or for Apache:
sudo certbot --apache -d bookforbook.com -d www.bookforbook.com
```

This obtains a free certificate and edits the nginx/Apache config automatically. Certificates renew automatically via a certbot cron job.

If you don't have sudo access, request SSL through the SureSupport control panel — most shared hosts offer one-click Let's Encrypt.

---

##### Step 6 — Collect static files

Django serves static files through the web server in production, not through itself:

```bash
cd ~/private/bookforbook
source .venv/bin/activate
python manage.py collectstatic --noinput
```

This copies all static files to `staticfiles/`. The nginx/Apache config above serves them directly from that directory.

---

##### Keeping gunicorn alive across reboots

Add a `@reboot` cron entry (`crontab -e`):

```
@reboot cd /home/bookforbook/private/bookforbook && /home/bookforbook/private/bookforbook/.venv/bin/gunicorn config.wsgi:application -c gunicorn.conf.py >> /home/bookforbook/logs/gunicorn-reboot.log 2>&1
```

---

##### Reloading after code updates

After `git pull` and `python manage.py migrate`:

```bash
kill -HUP $(cat /tmp/bookforbook.pid)
```

This gracefully restarts workers with no dropped connections. Or reattach to the screen session and restart manually (causes a few seconds of downtime).

---

##### Periodic tasks are run via cron (no background worker needed)

See the crontab entries in `SUPERUSER.md` under **Cron Schedule Reference**.

### 5. Frontend

```bash
cd frontend
npm install
npm run dev
```

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
