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
| Task queue | Celery + Redis |
| Frontend | React 18 (Vite) as PWA |
| ISBN data | Open Library API |
| Auth | JWT (djangorestframework-simplejwt) |
| File storage | S3-compatible |
| Notifications | Email (SendGrid/AWS SES), optional SMS (Twilio) |

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 20+
- Redis
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
REDIS_URL=redis://localhost:6379/0
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

```bash
# Django dev server
python manage.py runserver

# Celery worker (separate terminal, with .venv activated)
celery -A config worker --pool=solo --concurrency=1 -l info

# Celery beat scheduler (separate terminal, with .venv activated)
celery -A config beat --pool=solo --concurrency=1 -l info
```

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
├── config/                  # Django project settings, Celery, URLs
├── apps/
│   ├── accounts/            # User model, auth, profiles
│   ├── books/               # Book cache, ISBN lookup, Open Library client
│   ├── inventory/           # Have-list (UserBook) and want-list (WishlistItem)
│   ├── matching/            # Direct match + exchange ring detection
│   ├── trading/             # Proposals, trades, shipment tracking
│   ├── donations/           # Institutional donation workflow
│   ├── ratings/             # 1-5 star ratings with rolling average
│   ├── notifications/       # Email/in-app notifications via Celery
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
