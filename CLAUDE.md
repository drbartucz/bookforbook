# CLAUDE.md — BookForBook

## Project Overview

BookForBook is a book bartering platform where users in the continental USA trade books 1-for-1 without money changing hands. Users list books they want to give away (by ISBN) with condition ratings, and books they want to receive. The system auto-detects mutual matches and exchange rings, facilitates trade agreements, and reveals shipping addresses only after both parties confirm. Verified libraries and bookstores can receive donations.

**Current status:** Early-stage — architecture fully documented, no source code yet. Follow the 8-phase build roadmap in `docs/bookswap-architecture.md`.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 5.x + Django REST Framework |
| Database | PostgreSQL 16 |
| Task queue | Celery + Redis |
| Frontend | React 18 (Vite) as PWA |
| ISBN enrichment | Open Library API (free, no key required) |
| Notifications | Email via SendGrid/AWS SES; optional SMS via Twilio |
| Search | PostgreSQL full-text search (upgrade to Meilisearch later if needed) |
| File storage | S3-compatible (AWS S3, Backblaze B2, or local dev) |
| Auth | JWT via `djangorestframework-simplejwt` |
| Deployment | Docker Compose on VPS, or managed (Railway/Render) |

---

## Repository Structure (Target — Not Yet Built)

```
bookforbook/
├── CLAUDE.md
├── README.md
├── manage.py
├── requirements.txt
├── docker-compose.yml
├── .env.example
├── docs/
│   └── bookswap-architecture.md     # Full architecture spec (read this first)
│
├── config/                          # Django project config
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   ├── celery.py
│   └── wsgi.py
│
├── apps/
│   ├── accounts/                    # User model, auth, profiles
│   ├── books/                       # Book cache, ISBN lookup, Open Library client
│   ├── inventory/                   # UserBooks (have-list), WishlistItems (want-list)
│   ├── matching/                    # Match detection engine (direct + ring)
│   ├── trading/                     # Proposals, Trades, Shipments
│   ├── donations/                   # Institutional donation workflow
│   ├── ratings/                     # Rating system + rolling average
│   ├── notifications/               # Email/in-app notifications, Celery tasks
│   └── messaging/                   # Structured trade messages
│
├── frontend/                        # React PWA (Vite + vite-plugin-pwa)
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/                # API client
│   │   └── store/                   # State management
│   ├── public/manifest.json
│   └── package.json
│
└── scripts/
    └── seed_data.py                 # Development seed script
```

---

## Data Models (13 Core Models)

All primary keys are UUIDs. All personal address fields are encrypted at rest.

### User
- `account_type`: `individual` | `library` | `bookstore`
- `email_verified`: required before any trading activity
- Address fields (`full_name`, `address_line_1`, `address_line_2`, `city`, `state`, `zip_code`) — **encrypted at rest**, only revealed to confirmed trade partners
- `max_active_matches = min(max(rating_count, 1), 10)` — capacity grows with ratings received
- Inactivity tracking: `inactivity_warned_1m`, `inactivity_warned_2m`, `books_delisted_at`

### Book (ISBN cache)
- Normalized to ISBN-13; ISBN-10 also stored for search
- Populated from Open Library API on first lookup, cached locally
- `authors` and `subjects` stored as JSONB arrays
- If Open Library has no data, store ISBN with nulls and prompt user for title/author

### UserBook (have-list entries)
- `condition`: `like_new` | `very_good` | `good` | `acceptable`
- `status`: `available` | `reserved` | `traded` | `donated` | `removed` | `delisted`
- Multiple copies of the same ISBN allowed — each is a separate row
- `delisted` = inactive user's books (auto-relisted on login)

### WishlistItem (want-list entries)
- `min_condition`: minimum acceptable condition
- Unique constraint on `(user_id, book_id)`
- Soft-disable via `is_active`

### Match + MatchLeg (auto-detected)
- `match_type`: `direct` (2 legs) | `ring` (3–5 legs)
- All legs must be accepted for the match to proceed
- Any declined leg cancels the match; system re-detects alternatives

### TradeProposal + TradeProposalItem (user-initiated)
- Always 1-for-1: exactly one item in each direction (enforce at API level)
- Supports counter-offers (new proposal linked to original)

### Donation (institutional, one-directional)
- Separate from trades: no shipping address needed for the institution as receiver

### Trade (execution record, created after confirmation)
- `source_type`: `match` | `proposal` | `donation`
- `auto_close_at = confirmed_at + 3 weeks`
- Weekly Celery task sends up to 3 rating reminders; auto-closes with `auto_closed` status if no rating submitted

### TradeShipment (one per direction)
- `status`: `pending` | `shipped` | `received` | `not_received`
- Both shipments tracked independently

### Rating
- 1–5 stars; `book_condition_accurate` boolean
- Only last 10 ratings used for `avg_recent_rating` (rolling window)
- Unique constraint: `(trade_id, rater_id)`

### TradeMessage (structured, not free-form chat)
- `message_type`: `shipping_update` | `question` | `issue_report` | `general_note` | `delay_notice`
- `metadata`: JSONB for type-specific structured data (e.g., tracking numbers)

---

## API Structure

All endpoints under `/api/v1/`. JWT auth required except browse/search/public profiles.

```
auth/           register, verify-email, login, refresh, password-reset
users/          me (CRUD + export + delete), :id/ (public profile), :id/ratings/
books/          lookup/ (ISBN), :id/, search/
my-books/       GET/POST/PATCH/DELETE (have-list)
wishlist/       GET/POST/PATCH/DELETE (want-list)
matches/        list, :id/, :id/accept/, :id/decline/
proposals/      list, create, :id/, accept, decline, counter
trades/         list, :id/, mark-shipped, mark-received, rate, messages/
donations/      list, offer, :id/accept/, :id/decline/
institutions/   list, :id/, :id/wanted/
browse/         available/, available/?q=, partner/:id/books/, shipping-estimate/:book_id/
```

---

## Key Business Rules

1. **Email verification required** before adding books, matching, or messaging. Browse is allowed without verification.

2. **Match capacity**: `max_active_matches = min(max(rating_count, 1), 10)`. New users get 1 active match slot; up to 10 for experienced traders. Checked before proposing any match.

3. **Address reveal**: Shipping addresses are encrypted and only decrypted/returned when a trade is in `confirmed` status or later AND the requester is a party to that trade.

4. **1-for-1 trades only**: Proposals must have exactly one item in each direction. Enforced at the API level.

5. **Auto-close**: 3 weeks after trade confirmation, if no ratings submitted, the trade auto-closes (`auto_closed` status). Books marked as `traded`, trade counts incremented. No rating recorded.

6. **Inactivity auto-delist**: 1-month warning email, 2-month final warning, 3-month auto-delist (books hidden from matching). Books auto-relist on next login.

7. **No dispute resolution**: The rating system is the sole accountability mechanism.

8. **Continental USA only**: `state` field validated against continental US states only.

9. **Ring size limit**: Exchange rings are limited to 5 participants for logistics manageability.

10. **Institutional accounts**: Libraries and bookstores only receive donations — they do NOT trade. They require admin approval via Django admin before they can participate.

---

## Core Workflows

### Matching Engine (Celery, triggered on new UserBook/WishlistItem + periodic 6h scan)

**Direct match:**
```
For each available UserBook owned by user A:
  Find users who want that book (condition met)
  For each such user C:
    Check if C has any book A wants (condition met)
    → Create Match (direct) with 2 MatchLegs
```

**Ring detection (3–5 users):**
```
Build directed graph: edge A→B if A has something B wants
Find cycles of length 3–5 using DFS/Johnson's algorithm
Filter: each leg must use a currently available UserBook
→ Create Match (ring) with N MatchLegs
```

**Ring decline & retry:**
```
If a leg is declined:
  → Remove that user from the ring
  → Re-run cycle detection with remaining users + full pool
  → If new ring found: create new Match, notify all
  → If no ring possible: cancel, release all UserBooks to 'available'
```

### Trade Confirmation Flow
```
Match detected → email + in-app notification to all parties
Each party accepts/declines their leg
ALL accept → create Trade, reveal addresses, mark UserBooks as 'reserved'
ANY decline → cancel match, UserBooks remain 'available'
```

### Shipping Estimate (utility, not a DB model)
- Estimated weight: ~1 lb per 400 pages
- USPS Media Mail base rate: ~$4–5 for first pound (update manually, annually)
- Store rate tiers in config table or settings file; **do NOT integrate a live shipping API**

---

## Open Library API Integration

```python
# Book data
GET https://openlibrary.org/isbn/{isbn}.json

# Cover image
GET https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg

# Search fallback
GET https://openlibrary.org/search.json?isbn={isbn}
```

No API key required. Rate-limit requests to avoid abuse. Cache all results locally.

---

## Django Conventions to Follow

- **App structure per feature**: each app has `models.py`, `serializers.py`, `views.py`, `urls.py`, and a `services/` directory for business logic
- **Settings split**: `config/settings/base.py`, `development.py`, `production.py`
- **UUID primary keys** on all models
- **ENUM fields**: use Django's `TextChoices` for status/type fields
- **Encrypted fields**: use `django-fernet-fields` or equivalent for address fields
- **Celery tasks**: defined in `tasks.py` per app; triggered via Django signals
- **Type hints**: use throughout Python code
- **Serializers validate**: all input at the API boundary; never trust raw request data

---

## Security Requirements

- JWT access tokens: 15-minute expiry; refresh tokens: 7-day expiry
- DRF throttling on all endpoints, especially `/api/v1/books/lookup/`
- Address fields encrypted at rest; never returned in API responses except to confirmed trade partners
- ISBN format validation, US state/ZIP validation, condition enum enforcement
- GDPR-compliant deletion: 30-day grace period, data export, anonymize ratings (keep scores, remove user reference)

---

## Development Setup (When Code Exists)

```bash
# Backend
cp .env.example .env
docker-compose up -d          # starts postgres, redis
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

# Celery worker (separate terminal)
celery -A config worker -l info

# Frontend
cd frontend
npm install
npm run dev
```

---

## Build Roadmap (8 Phases)

See `docs/bookswap-architecture.md` for full details.

| Phase | Focus |
|-------|-------|
| 1 | Django scaffold, Docker, User model, auth endpoints, Open Library |
| 2 | UserBook + WishlistItem CRUD, browse/search |
| 3 | Direct match detection, match limits, accept/decline + address reveal |
| 4 | Trade proposals, shipment tracking, messaging, ratings, auto-close |
| 5 | Institutional accounts, donation workflow |
| 6 | Exchange ring detection, ring decline/retry, multi-party confirmation |
| 7 | Inactivity management, GDPR export + deletion |
| 8 | PWA frontend, email templates, rate limiting, production config |

**Start at Phase 1 unless instructed otherwise.** Complete each phase fully before moving to the next.

---

## Key Files to Know

| File | Purpose |
|------|---------|
| `docs/bookswap-architecture.md` | Complete architecture specification — read before implementing anything |
| `config/settings/base.py` | Django base settings (to be created) |
| `config/celery.py` | Celery app configuration (to be created) |
| `apps/matching/services/direct_matcher.py` | Direct match detection logic (to be created) |
| `apps/matching/services/ring_detector.py` | Exchange ring cycle detection (to be created) |
| `apps/books/services/openlibrary.py` | Open Library API client (to be created) |
| `apps/ratings/services/rolling_average.py` | Rolling average recomputation (to be created) |
| `apps/notifications/tasks.py` | All Celery notification tasks (to be created) |
