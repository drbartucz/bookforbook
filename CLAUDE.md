# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend

```bash
# Run dev server
python manage.py runserver

# Run background task worker (Django-Q2; required for matching, notifications, backups)
python manage.py qcluster

# Run all tests
pytest

# Run a single test file
pytest apps/matching/tests/test_matching.py

# Run a single test by name
pytest apps/matching/tests/test_matching.py::TestDirectMatch::test_basic_match

# Run tests by marker
pytest -m unit
pytest -m api

# Run migrations after model changes
python manage.py makemigrations
python manage.py migrate

# Seed development data
python scripts/seed_data.py
```

`DJANGO_SETTINGS_MODULE` defaults to `config.settings.development` (set in `pytest.ini` and expected locally). Coverage threshold is 70%.

### Frontend

```bash
cd frontend
npm run dev          # Vite dev server (proxies /api to localhost:8000)
npm run test         # Vitest in watch mode
npm run test:run     # Vitest single run
npm run build        # Production build (also copies dist/index.html → dist/404.html)
npm run e2e          # Playwright critical tests
```

### Required env vars for local dev

Minimum `.env` (copy from `.env.example`):
- `SECRET_KEY`
- `DATABASE_URL` — `postgresql://bookforbook:bookforbook@localhost:5432/bookforbook`
- `FIELD_ENCRYPTION_KEY` — Fernet key (required; generates encrypted address fields)
- `MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS=0`

---

## Architecture

### Backend structure

Each Django app follows a consistent layout: `models.py`, `serializers.py`, `views.py`, `urls.py`, and a `services/` directory for business logic. Keep business logic out of views and serializers — it belongs in `services/`.

Background tasks are defined in `tasks.py` per app and dispatched via `django_q.tasks.async_task()`. Tasks are triggered by Django signals or the Django-Q2 scheduler.

| App | Responsibility |
|-----|---------------|
| `accounts` | Custom `User` model, JWT auth, email verification, USPS address verification, inactivity tracking, GDPR export/delete |
| `books` | `Book` ISBN cache populated from Open Library API; normalized to ISBN-13 |
| `inventory` | `UserBook` (have-list) and `WishlistItem` (want-list) |
| `matching` | Direct match and exchange ring detection; triggered on new UserBook/WishlistItem and on a 6-hour periodic scan |
| `trading` | `TradeProposal`, `Trade`, `TradeShipment`, `TradeMessage`; shipment tracking and trade lifecycle |
| `donations` | One-directional book donations to institutional accounts |
| `ratings` | 1–5 star ratings; rolling average over last 10 ratings via `apps/ratings/services/rolling_average.py` |
| `notifications` | Email and in-app notifications dispatched as Django-Q2 tasks |
| `messaging` | Structured trade messages (not free-form chat) |
| `backups` | Nightly database backups to Backblaze B2; admin-triggered manual backup/restore |

### User model (`apps/accounts/models.py`)

- UUID primary key on all models throughout the codebase
- All address fields (`full_name`, `address_line_1`, `address_line_2`) use `EncryptedCharField` (django-encrypted-model-fields, Fernet). These are never returned in API responses except to confirmed trade partners.
- `account_type`: `individual` | `library` | `bookstore`
- `is_institutional` property: true for library/bookstore accounts
- `max_active_matches = min(max(rating_count, 2), 10)` — match capacity grows with trade history
- `last_active_at` is updated only on successful login (not on every request)

### Matching engine (`apps/matching/services/`)

Two detection paths, both skip institutional users:

**Direct match** (`direct_matcher.py`): A has something B wants + B has something A wants. Uses a two-phase approach — exact-edition wishlist entries are evaluated before related-edition entries (same language, any language, custom). Priority within each phase: oldest wishlist entry first, then stricter minimum condition, then UUID tie-break.

**Ring detection** (`ring_detector.py`): Builds a directed graph of who has what others want, then finds cycles of 3–5 users using DFS. Filters to only `individual` account types. If one leg of a ring is declined, the system attempts to reform a new ring before cancelling.

**Reverse Discovery** (`ReverseDiscoveryView`): A manual discovery path that finds users who want the current user's available books, even if a mutual match hasn't been auto-detected. Filtered results include partners' available books and what they want from the current user.

Match capacity is checked before creating any match or accepting any proposal. Address verification is required before accepting a match or proposal.

### Trade lifecycle

```
Match detected → all parties notified
  → each accepts/declines their leg
  → ALL accept → Trade created, addresses revealed, UserBooks → 'reserved'
  → ANY decline → match cancelled, UserBooks → 'available'

Trade confirmed → 3-week auto-close timer starts
  → weekly rating reminders (up to 3)
  → no rating after 3 weeks → auto_closed, books marked 'traded'
```

`Trade.source_type`: `match` | `proposal` | `donation`

### Institutional accounts (libraries/bookstores)

Institutions require admin approval (`is_verified=True`) before participating. They are excluded from automated match detection but **can** list books on their have-list and participate in manual trade proposals. They also receive donations.

### Frontend (`frontend/`)

React 18 PWA built with Vite. State: Zustand. Server state: TanStack Query. Forms: react-hook-form. HTTP: axios. Routes: react-router-dom v6. UI: Radix UI primitives.

The Vite dev server proxies `/api` to `http://localhost:8000` automatically — no CORS issues in local dev.

### Key conventions

- All enum/choice fields use Django `TextChoices`
- Type hints throughout Python code
- Serializers validate all input at the API boundary
- `TextChoices` statuses follow a consistent pattern: check `apps/trading/models.py` or `apps/matching/models.py` for examples
- Shipping cost estimates use hardcoded USPS Media Mail rate tiers — do **not** integrate a live shipping API
- Exchange ring size is capped at 5 participants
- Frontend styling uses vanilla CSS with CSS Modules (`.module.css`) — no CSS-in-JS or utility frameworks
- New endpoints requiring auth should apply `EmailVerifiedPermission` and check `user_has_verified_shipping_address` where address is needed
- Do not make any functional or UI changes beyond what the user explicitly requests without asking first.