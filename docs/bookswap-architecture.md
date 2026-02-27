# BookForBook — Architecture & Data Model

## Overview

BookForBook is a book bartering platform where users trade books 1-for-1 without money changing hands. Users list books they want to give away (by ISBN) with condition ratings, and list books they want to receive. The system auto-detects mutual matches and exchange rings, facilitates trade agreements, and reveals mailing addresses only after both parties confirm. Verified libraries and second-hand bookstores can also create profiles with wanted lists to receive donations. All users must be in the continental USA.

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Backend framework | Django 5.x + Django REST Framework | Auth, ORM, admin panel out of the box; strong Python ecosystem |
| Database | PostgreSQL 16 | Relational data model, full-text search, JSON fields for flexibility |
| Task queue | Celery + Redis | Background matching engine, email notifications, ISBN enrichment |
| Frontend | React 18 (Vite) as PWA | Interactive browsing, trade flows; PWA for mobile access |
| ISBN enrichment | Open Library API (free, no key required) | Title, author, cover image, publisher, year, page count |
| Notifications | Email (Django + SendGrid/SES), SMS optional (Twilio) | Trade alerts, match notifications, shipping confirmations |
| Search | PostgreSQL full-text search (upgrade to Meilisearch/Typesense if needed) | Book catalog browsing |
| File storage | S3-compatible (AWS S3, Backblaze B2, or local for dev) | Cover image caching |
| Deployment | VPS with Docker Compose OR managed (Railway, Render) | Flexible based on preference |

---

## Data Model

### Users

```
User
├── id                  UUID, primary key
├── email               unique, indexed
├── email_verified      boolean, default false
├── email_verified_at   nullable timestamp
├── username            unique, indexed, public-facing
├── password_hash       via Django auth
├── account_type        ENUM: 'individual', 'library', 'bookstore'
├── is_verified         boolean (for institutional accounts, admin-approved)
├── institution_name    nullable, for libraries/bookstores
├── institution_url     nullable, website for verification
│
├── # Shipping (revealed only after trade confirmation)
├── full_name           encrypted at rest
├── address_line_1      encrypted at rest
├── address_line_2      encrypted at rest
├── city                string
├── state               CHAR(2), validated to continental US states
├── zip_code            validated US ZIP
│
├── # Public profile stats (denormalized for performance)
├── total_trades        integer, default 0
├── avg_recent_rating   decimal, computed from last 10 ratings
├── rating_count        integer, default 0
├── max_active_matches  computed: min(max(rating_count, 1), 10)
│
├── # Inactivity tracking
├── inactivity_warned_1m  nullable timestamp (1-month warning sent)
├── inactivity_warned_2m  nullable timestamp (2-month warning sent)
├── books_delisted_at     nullable timestamp (3-month auto-delist)
│
├── created_at          timestamp
├── updated_at          timestamp
└── last_active_at      timestamp
```

**Notes:**
- Institutional accounts (`library`, `bookstore`) have a verification workflow: they register, provide institution details, and an admin approves via Django admin.
- Institutional accounts do NOT trade — they only receive donations, so they don't need a "have" list or shipping address for outbound.
- Address fields are encrypted at rest and only decrypted/revealed to a confirmed trade partner.

### Books (ISBN Cache)

```
Book
├── id                  UUID, primary key
├── isbn_13             CHAR(13), unique, indexed (normalized to ISBN-13)
├── isbn_10             CHAR(10), nullable, indexed
├── title               string
├── authors             JSONB array of strings
├── publisher           nullable string
├── publish_year        nullable integer
├── cover_image_url     nullable URL (Open Library cover)
├── cover_image_cached  nullable string (local/S3 path if cached)
├── page_count          nullable integer
├── subjects            JSONB array of strings (for browse/filter)
├── description         nullable text
├── open_library_key    nullable string (e.g., "/works/OL12345W")
│
├── created_at          timestamp
└── updated_at          timestamp
```

**Notes:**
- Populated via Open Library API on first ISBN entry; cached locally.
- If Open Library has no data, store the ISBN with nulls and let the user manually enter title/author.
- ISBN-10 is auto-converted to ISBN-13 for consistency; both are stored for search.

### UserBooks (Books Available for Trade/Donation)

```
UserBook
├── id                  UUID, primary key
├── user_id             FK → User, indexed
├── book_id             FK → Book, indexed
├── condition           ENUM: 'like_new', 'very_good', 'good', 'acceptable'
├── condition_notes     nullable text (e.g., "slight crease on cover")
├── status              ENUM: 'available', 'reserved', 'traded', 'donated',
│                              'removed', 'delisted'
│
├── created_at          timestamp
└── updated_at          timestamp

INDEX: (user_id, book_id, status) — for querying a user's listings of a specific book
INDEX: (book_id, status) — for matching queries
INDEX: (status, created_at) — for browsing available books
```

**Notes:**
- `reserved` means a trade/donation has been proposed and accepted but not yet completed.
- `traded`/`donated` are terminal states.
- `delisted` means the user has been inactive for 3+ months. Books remain in their account but are hidden from browse/matching. Re-listing happens automatically when the user logs back in.
- Users **can list multiple copies** of the same book — each with its own condition and notes. No unique constraint on (user_id, book_id); each copy is a separate UserBook row.

### WishlistItems (Books a User Wants)

```
WishlistItem
├── id                  UUID, primary key
├── user_id             FK → User, indexed
├── book_id             FK → Book, indexed
├── min_condition       ENUM: 'like_new', 'very_good', 'good', 'acceptable'
│                       (minimum acceptable condition, default 'acceptable')
├── is_active           boolean, default true
│
├── created_at          timestamp
└── updated_at          timestamp

UNIQUE CONSTRAINT: (user_id, book_id)
INDEX: (book_id, is_active) — for matching queries
```

**Notes:**
- For institutional accounts, this is their "wanted for donation" list.
- `is_active` allows soft-disable without deletion (e.g., "I got this from a store, pause for now").

### Matches (Auto-Detected)

```
Match
├── id                  UUID, primary key
├── match_type          ENUM: 'direct', 'ring'
├── status              ENUM: 'pending', 'proposed', 'expired', 'completed'
├── detected_at         timestamp
├── expires_at          timestamp (auto-expire if not acted on)
└── updated_at          timestamp

MatchLeg (each leg of a match — who sends what to whom)
├── id                  UUID, primary key
├── match_id            FK → Match, indexed
├── sender_id           FK → User
├── receiver_id         FK → User
├── user_book_id        FK → UserBook
├── position            integer (order in ring, 0 for direct matches)
└── status              ENUM: 'pending', 'accepted', 'declined'

INDEX on Match: (status, detected_at)
INDEX on MatchLeg: (sender_id, status), (receiver_id, status)
```

**Notes:**
- A **direct match** has exactly 2 legs: A→B and B→A.
- An **exchange ring** has 3+ legs: A→B, B→C, C→A.
- A match moves to `proposed` when the system notifies users. All legs must be `accepted` for the match to proceed.
- If any leg is `declined`, the entire match is cancelled and re-detection can find alternatives.

### TradeProposals (User-Initiated, Including Post-Match Browse)

```
TradeProposal
├── id                  UUID, primary key
├── proposer_id         FK → User
├── recipient_id        FK → User
├── origin_match_id     nullable FK → Match (if spawned from browsing a match partner's list)
├── status              ENUM: 'pending', 'accepted', 'declined', 'countered',
│                              'cancelled', 'completed'
├── message             nullable text (personal note)
│
├── created_at          timestamp
├── updated_at          timestamp
└── expires_at          timestamp

TradeProposalItem
├── id                  UUID, primary key
├── proposal_id         FK → TradeProposal, indexed
├── direction           ENUM: 'proposer_sends', 'recipient_sends'
├── user_book_id        FK → UserBook
└── created_at          timestamp
```

**Notes:**
- A user can propose a trade independently of the matching engine (from browsing).
- After a direct match is confirmed, users can browse each other's full lists and create additional `TradeProposal` records linked via `origin_match_id`.
- Counter-offers create a new proposal with a reference to the original.
- Must be 1-for-1: exactly one item in each direction per proposal (enforce at API level).

### Donations (Institutional)

```
Donation
├── id                  UUID, primary key
├── donor_id            FK → User (individual)
├── institution_id      FK → User (library/bookstore, must be verified)
├── user_book_id        FK → UserBook
├── status              ENUM: 'offered', 'accepted', 'shipped', 'received', 'cancelled'
├── message             nullable text
│
├── created_at          timestamp
└── updated_at          timestamp
```

**Notes:**
- Separate from trades because donations are one-directional.
- Institutions can accept/decline offers.
- Shipping address reveal follows the same pattern as trades (only after acceptance).

### Trades (Confirmed Exchanges — The Execution Record)

```
Trade
├── id                  UUID, primary key
├── source_type         ENUM: 'match', 'proposal', 'donation'
├── source_id           UUID (FK to Match, TradeProposal, or Donation)
├── status              ENUM: 'confirmed', 'shipping', 'one_received',
│                              'completed', 'auto_closed'
│
├── created_at          timestamp
├── updated_at          timestamp
├── completed_at        nullable timestamp
├── auto_close_at       nullable timestamp (set to confirmed_at + 3 weeks)
└── rating_reminders_sent  integer, default 0 (0, 1, 2, or 3 weekly reminders)

TradeShipment (one per direction in the trade)
├── id                  UUID, primary key
├── trade_id            FK → Trade, indexed
├── sender_id           FK → User
├── receiver_id         FK → User
├── user_book_id        FK → UserBook
├── tracking_number     nullable string
├── shipping_method     nullable string (free text, e.g., "USPS Media Mail")
├── shipped_at          nullable timestamp
├── received_at         nullable timestamp
├── status              ENUM: 'pending', 'shipped', 'received', 'not_received'
└── created_at          timestamp
```

**Notes:**
- This is created when a match/proposal/donation is fully confirmed.
- Address is revealed to both parties at this point.
- Each shipment is tracked independently — one side might ship before the other.
- `one_received` means one party confirmed receipt; `completed` means both have.
- **Auto-close logic:** After a match is accepted, a weekly Celery task sends rating reminders to users who haven't rated yet (up to 3 reminders). After 3 weeks with no rating, the trade is auto-closed with status `auto_closed` — the book is assumed received, UserBooks move to `traded`, and user trade counts are updated. No rating is recorded.
- **No dispute resolution.** The rating system is the only accountability mechanism. Users who send wrong books or don't ship will accumulate bad ratings.

### Ratings

```
Rating
├── id                  UUID, primary key
├── trade_id            FK → Trade (each trade generates up to 2 ratings)
├── rater_id            FK → User
├── rated_id            FK → User
├── score               INTEGER, 1-5
├── comment             nullable text (max 500 chars)
├── book_condition_accurate  boolean (did the book match its listed condition?)
│
├── created_at          timestamp
└── updated_at          timestamp

UNIQUE CONSTRAINT: (trade_id, rater_id) — one rating per user per trade
```

**Notes:**
- Only the **last 10 ratings** are used for computing `avg_recent_rating` on the User profile.
- Historical ratings are kept in the database but not surfaced publicly.
- A Celery task or DB trigger recomputes the rolling average after each new rating.
- `book_condition_accurate` helps build trust signals beyond the star rating.

### Shipping Estimates

Shipping cost is borne by the sender. The platform displays a **general estimate** based on USPS Media Mail rates and the book's page count (as a weight proxy), but makes it clear this is approximate and **any shipping method is acceptable**.

```
ShippingEstimate (utility — not a DB model, computed on the fly)
├── Input: page_count (from Book record)
├── Estimated weight: ~1 lb per 400 pages (rough heuristic)
├── USPS Media Mail base rate: ~$4-5 for first pound (update periodically)
├── Output: "Estimated shipping: $4–6 via USPS Media Mail"
```

**UI copy:** "Shipping is the sender's responsibility. USPS Media Mail is the most affordable option for books — we estimate this shipment around **$X–Y** — but you're free to use any carrier or method you prefer. This is only a rough estimate."

**Implementation:** Store current Media Mail rate tiers in a config table or settings file. Update manually when USPS adjusts rates (typically annually). Do NOT integrate a live shipping API — keep this lightweight.

### Structured Messages

Communication between trade partners uses structured message types rather than free-form chat. This keeps interactions focused and extensible.

```
TradeMessage
├── id                  UUID, primary key
├── trade_id            FK → Trade, indexed
├── sender_id           FK → User
├── message_type        ENUM: 'shipping_update', 'question', 'issue_report',
│                              'general_note', 'delay_notice'
├── content             text (max 1000 chars)
├── metadata            JSONB, nullable (e.g., {"tracking_number": "...",
│                       "carrier": "USPS"} for shipping updates)
│
├── created_at          timestamp
└── read_at             nullable timestamp

INDEX: (trade_id, created_at)
```

**Notes:**
- The `message_type` enum is designed to be extended — new types can be added without schema changes.
- `metadata` JSONB allows type-specific structured data (tracking info for shipping updates, etc.).
- No threading or replies for now — messages are a flat chronological list per trade.
- Future expansion: add types like `address_correction`, `condition_dispute`, `thanks`, etc.

---

## Core Workflows

### 1. Adding Books (Have / Want)

```
User enters ISBN
    → Normalize to ISBN-13
    → Check Book cache table
    → If not found: call Open Library API, create Book record
    → If Open Library has no data: create Book with ISBN only, prompt user for title/author
    → User selects condition (for "have") or min condition (for "want")
    → Create UserBook or WishlistItem
    → Trigger async matching scan for this user
```

**Open Library API endpoints:**
- Book data: `https://openlibrary.org/isbn/{isbn}.json`
- Cover image: `https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg`
- Search fallback: `https://openlibrary.org/search.json?isbn={isbn}`

### 2. Matching Engine (Background — Celery)

**Runs on triggers:**
- New UserBook or WishlistItem created
- Periodic full scan (e.g., every 6 hours)

**Direct match detection:**
```
For a given user A:
    For each book B in A's have-list (status=available):
        Find users who want book B (WishlistItem, active, condition met)
        For each such user C:
            Check if C has any book that A wants (WishlistItem, active, condition met)
            If yes → Create Match (type=direct) with 2 MatchLegs
```

**Exchange ring detection:**
```
Build directed graph:
    Nodes = users with both have and want items
    Edge A→B exists if A has something B wants (condition met)

Find cycles of length 3-5:
    Use DFS-based cycle detection or Johnson's algorithm
    Filter: each leg must involve a currently available UserBook
    Create Match (type=ring) with N MatchLegs

Optimization: limit ring size to 5 to keep logistics manageable
```

**Ring decline & retry:**
```
If any leg in a ring is declined:
    → Remove the declining user from the ring
    → Re-run cycle detection on remaining participants + full user pool
    → If a valid replacement ring is found:
        → Create new Match, notify all parties
    → If no valid ring can be formed:
        → Cancel the match entirely
        → Notify all users that the ring could not be completed
        → Release all involved UserBooks back to 'available'
        → These books re-enter the next matching scan
```

**Deduplication:**
- Don't create a match if an equivalent active match already exists.
- A UserBook can only be in one active (pending/proposed) match at a time.

### 3. Trade Confirmation Flow

```
Match detected → Notify all parties (email/in-app)
    → Each party reviews and accepts/declines their leg
    → If ALL accept:
        → Create Trade record
        → Reveal shipping addresses to involved parties
        → Mark involved UserBooks as 'reserved'
    → If ANY decline:
        → Cancel match
        → UserBooks remain available for future matching
```

### 4. Post-Match Browse & Propose (Direct Matches Only)

```
After a direct match is confirmed:
    → Both users see a prompt: "Browse [partner]'s full list for more trades?"
    → User can view partner's available books (minus the one already in the trade)
    → User can propose additional 1-for-1 trades via TradeProposal
    → Standard proposal accept/decline flow
```

### 5. Donation Flow (Institutional)

```
Individual browses institution's wanted list
    OR institution's wanted book appears in individual's have-list
    → Individual offers to donate
    → Institution accepts/declines
    → If accepted: create Trade (source_type=donation), reveal address
    → Individual ships book
    → Institution confirms receipt
    → (No rating for donations? Or optional rating of donor reliability?)
```

### 6. Rating & Auto-Close Flow

```
After a trade is confirmed:
    → Set auto_close_at = confirmed_at + 3 weeks
    → Weekly Celery task checks all active trades:
        → If user hasn't rated AND trade is still open:
            → Send rating reminder email (up to 3 per user)
            → Increment rating_reminders_sent
        → If auto_close_at has passed AND trade is not completed:
            → Set status = 'auto_closed'
            → Mark all shipments as 'received' (assumed)
            → Mark UserBooks as 'traded'
            → Increment User.total_trades for both parties
            → No rating is recorded

When a user DOES submit a rating:
    → Score (1-5) + optional comment + condition accuracy
    → Recompute rated user's rolling average (last 10 ratings)
    → Update User.avg_recent_rating, User.rating_count
    → If both users have rated → status = 'completed'
```

**Rolling average computation:**
```sql
SELECT AVG(score) FROM (
    SELECT score FROM ratings
    WHERE rated_id = :user_id
    ORDER BY created_at DESC
    LIMIT 10
) AS recent;
```

### 7. Match Limit Enforcement

Users earn match capacity through completed trades with ratings:

```
New user (0 ratings):       1 active match at a time
After 1st rating received:  1 active match
After 2nd rating:           2 active matches
After 3rd rating:           3 active matches
...
After 10+ ratings:          10 active matches (maximum)

Formula: max_active_matches = min(max(rating_count, 1), 10)
```

**Enforcement:**
- Checked when the system proposes a match or a user creates a trade proposal.
- "Active match" = any Match or TradeProposal in a non-terminal state (pending, proposed, accepted, shipping).
- If a user is at their limit, new matches involving them are deferred (not lost — re-detected on next scan after a slot opens).

### 8. Email Verification

```
User registers with email + password
    → Account created with email_verified = false
    → Verification email sent with signed token (expires in 24h)
    → User clicks link → POST /api/v1/auth/verify-email/
    → email_verified = true, email_verified_at = now()
    → Until verified: user can browse but CANNOT:
        - Add books to have/want lists
        - Participate in matches or proposals
        - Send messages
```

### 9. Inactivity Management

```
Daily Celery task scans all users:

1 month since last_active_at (no warning sent yet):
    → Send "We miss you" email with summary of any pending matches
    → Set inactivity_warned_1m = now()

2 months since last_active_at (1m warning sent, no 2m warning):
    → Send "Your books will be delisted" warning email
    → Set inactivity_warned_2m = now()

3 months since last_active_at (2m warning sent):
    → Set all user's 'available' UserBooks to 'delisted'
    → Set books_delisted_at = now()
    → Books are hidden from browse and matching
    → Books remain in the user's account

When user logs back in after delisting:
    → Set all 'delisted' UserBooks back to 'available'
    → Clear inactivity warning timestamps
    → Books re-enter matching pool on next scan
```

### 10. Account Deletion (GDPR)

```
User requests deletion → POST /api/v1/users/me/ (DELETE)
    → Require password confirmation
    → Immediately:
        - Cancel all active matches/proposals involving this user
        - Notify affected trade partners
    → Generate data export (JSON) and email to user:
        - All UserBooks, WishlistItems, Trades, Ratings (given and received),
          Messages, profile data
    → After 30-day grace period (user can cancel deletion):
        - Hard delete: user record, personal data, address, messages
        - Anonymize: ratings given/received (keep scores, remove user reference)
        - Remove: all UserBooks, WishlistItems
        - Cascade: remove user from any historical match records
```

---

## API Structure (Django REST Framework)

```
/api/v1/
├── auth/
│   ├── POST   register/              # Create account (sends verification email)
│   ├── POST   verify-email/          # Confirm email via token
│   ├── POST   login/                 # JWT token pair (requires verified email)
│   ├── POST   refresh/               # Refresh token
│   └── POST   password-reset/        # Email-based reset
│
├── users/
│   ├── GET    me/                     # Current user profile
│   ├── PATCH  me/                     # Update profile/address
│   ├── GET    me/export/              # GDPR data export (all user data as JSON)
│   ├── DELETE me/                     # GDPR account deletion (requires confirmation)
│   ├── GET    :id/                    # Public profile (stats, ratings, no address)
│   └── GET    :id/ratings/            # Last 10 ratings for user
│
├── books/
│   ├── POST   lookup/                 # ISBN lookup → returns/creates Book
│   ├── GET    :id/                    # Book detail
│   └── GET    search/                 # Search by title, author, ISBN
│
├── my-books/
│   ├── GET    /                       # My have-list
│   ├── POST   /                       # Add book (ISBN + condition)
│   ├── PATCH  :id/                    # Update condition/notes
│   └── DELETE :id/                    # Remove from list
│
├── wishlist/
│   ├── GET    /                       # My want-list
│   ├── POST   /                       # Add to wishlist (ISBN + min condition)
│   ├── PATCH  :id/                    # Update preferences
│   └── DELETE :id/                    # Remove from wishlist
│
├── matches/
│   ├── GET    /                       # My pending/active matches
│   ├── GET    :id/                    # Match detail (legs, books, users)
│   ├── POST   :id/accept/            # Accept my leg
│   └── POST   :id/decline/           # Decline my leg
│
├── proposals/
│   ├── GET    /                       # My proposals (sent and received)
│   ├── POST   /                       # Create trade proposal
│   ├── GET    :id/                    # Proposal detail
│   ├── POST   :id/accept/            # Accept proposal
│   ├── POST   :id/decline/           # Decline proposal
│   └── POST   :id/counter/           # Counter-offer
│
├── trades/
│   ├── GET    /                       # My active/completed trades
│   ├── GET    :id/                    # Trade detail (with address if confirmed)
│   ├── POST   :id/mark-shipped/      # Mark my shipment as sent
│   ├── POST   :id/mark-received/     # Confirm I received the book
│   ├── POST   :id/rate/              # Submit rating
│   ├── GET    :id/messages/          # Structured messages for this trade
│   └── POST   :id/messages/          # Send a structured message
│
├── donations/
│   ├── GET    /                       # My donations (as donor or institution)
│   ├── POST   /                       # Offer a donation
│   ├── POST   :id/accept/            # Institution accepts
│   └── POST   :id/decline/           # Institution declines
│
├── institutions/
│   ├── GET    /                       # Browse verified institutions
│   ├── GET    :id/                    # Institution profile
│   └── GET    :id/wanted/            # Institution's wanted list
│
└── browse/
    ├── GET    available/              # Browse all available books
    ├── GET    available/?q=...        # Search available books
    ├── GET    partner/:id/books/      # Browse a confirmed trade partner's list
    └── GET    shipping-estimate/:book_id/  # Approximate Media Mail cost
```

---

## Notification Strategy

| Event | Channel | Priority |
|-------|---------|----------|
| Email verification | Email | Critical |
| New match detected | Email + in-app | High |
| Trade proposal received | Email + in-app | High |
| Trade confirmed (address revealed) | Email | High |
| Partner marked as shipped | Email + in-app | Medium |
| Weekly rating reminder (up to 3) | Email | Medium |
| Trade auto-closed (3 weeks, no rating) | Email + in-app | Medium |
| Rating received | In-app | Low |
| Match expired (no action taken) | Email | Medium |
| Donation offer received (institution) | Email + in-app | Medium |
| Inactivity warning — 1 month | Email | Medium |
| Inactivity warning — 2 months (delist soon) | Email | High |
| Books delisted — 3 months | Email | High |
| Account deletion initiated (30-day grace) | Email | Critical |
| Account deletion completed | Email | Critical |

**Implementation:** Celery tasks triggered by Django signals. Email via SendGrid or AWS SES. In-app via a simple Notification model polled by frontend (upgrade to WebSockets later if needed).

---

## Security Considerations

- **Address privacy:** Encrypted at rest (Django Fernet fields or similar). Only decrypted and returned via API when a trade is in `confirmed` or later status AND the requesting user is a party to that trade.
- **Rate limiting:** Django REST Framework throttling on all endpoints, especially ISBN lookup (prevent abuse of Open Library API).
- **Authentication:** JWT via `djangorestframework-simplejwt`. Short-lived access tokens (15 min), longer refresh tokens (7 days). Email verification required before any trading activity.
- **Input validation:** ISBN format validation, US state/ZIP validation, condition enum enforcement.
- **Abuse prevention:** No formal dispute resolution — the rating system is the sole accountability mechanism. Match limits (tied to rating count) naturally throttle new users and reward trusted ones. Users who consistently receive poor ratings will be visible to potential trade partners.

---

## Project Structure (Django)

```
bookforbook/
├── manage.py
├── requirements.txt
├── docker-compose.yml
├── .env.example
│
├── config/                     # Django project settings
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   ├── celery.py
│   └── wsgi.py
│
├── apps/
│   ├── accounts/               # User model, auth, profiles
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── signals.py
│   │
│   ├── books/                  # Book cache, ISBN lookup
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── services/
│   │       └── openlibrary.py  # API client
│   │
│   ├── inventory/              # UserBooks, WishlistItems
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── urls.py
│   │
│   ├── matching/               # Match detection engine
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── services/
│   │       ├── direct_matcher.py
│   │       └── ring_detector.py
│   │
│   ├── trading/                # Proposals, Trades, Shipments
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── services/
│   │       └── trade_workflow.py
│   │
│   ├── donations/              # Institutional donations
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── urls.py
│   │
│   ├── ratings/                # Rating system
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── services/
│   │       └── rolling_average.py
│   │
│   ├── notifications/          # Email, in-app notifications
│       ├── models.py
│       ├── tasks.py            # Celery tasks
│       └── templates/          # Email templates
│
│   └── messaging/              # Structured trade messages
│       ├── models.py
│       ├── serializers.py
│       ├── views.py
│       └── urls.py
│
├── frontend/                   # React PWA (Vite + vite-plugin-pwa)
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/           # API client
│   │   └── store/              # State management
│   ├── public/
│   │   └── manifest.json       # PWA manifest
│   └── package.json
│
└── scripts/
    └── seed_data.py            # Development seed script
```

---

## Claude Code Strategy

This architecture is designed to be built incrementally with Claude Code. Recommended build order:

### Phase 1 — Foundation
1. Django project scaffold with settings, Docker Compose (Postgres + Redis)
2. Custom User model with account types and email verification fields
3. Auth endpoints: register, login, email verification, password reset
4. Book model + Open Library API service
5. Basic ISBN lookup endpoint

### Phase 2 — Core Inventory
6. UserBook and WishlistItem models + CRUD endpoints
7. ISBN entry flow (lookup → create book → add to list)
8. Browse available books with search/filter

### Phase 3 — Matching Engine
9. Direct match detection service + Celery task
10. Match model + notification on match
11. Match limit enforcement (rating-based capacity)
12. Accept/decline flow with address reveal

### Phase 4 — Trading & Communication
13. Trade proposal system (independent of matching)
14. Trade execution (shipment tracking, receipt confirmation)
15. Structured messaging system (shipping updates, questions, issue reports)
16. Shipping estimate utility (Media Mail rate lookup by page count)
17. Post-match partner browsing + additional proposals
18. Rating system with rolling average
19. Weekly rating reminder Celery task
20. 3-week auto-close logic for unrated trades

### Phase 5 — Institutions
21. Institutional registration + admin verification
22. Donation workflow
23. Institution browse/search

### Phase 6 — Exchange Rings
24. Ring detection algorithm (cycle-finding)
25. Ring decline & retry logic (re-detection, fallback notification)
26. Multi-party match confirmation flow
27. Ring trade execution

### Phase 7 — User Lifecycle
28. Inactivity detection Celery task (1m/2m warnings, 3m delist)
29. Auto-relist on login after delisting
30. GDPR data export endpoint
31. Account deletion with 30-day grace period and anonymization

### Phase 8 — Polish & PWA
32. PWA setup (manifest, service worker, offline support, install prompt)
33. Frontend build-out (responsive design for mobile/desktop)
34. Email notification templates (verification, matches, reminders, inactivity, deletion)
35. Rate limiting, abuse prevention
36. Production deployment config

---

## Decisions Made

- **Shipping costs:** Sender pays. Platform shows a rough Media Mail estimate based on page count, with clear messaging that any shipping method is acceptable and the estimate is approximate.
- **Multi-copy support:** Yes — users can list multiple copies of the same ISBN, each with its own condition rating and notes.
- **Ring decline handling:** System attempts to re-form the ring without the declining user. If no valid ring can be formed, all participants are notified and their books return to the available pool.
- **Messaging:** Structured message types only (shipping updates, questions, issue reports, etc.). Extensible via enum — no free-form chat for now.
- **Mobile access:** PWA via Vite + vite-plugin-pwa. No native app.
- **Geographic proximity:** No prioritization of local matches.
- **Book clubs / collections:** Not in scope for initial build.
- **Email verification:** Required before any trading activity. Users can browse without verification.
- **Account deletion:** Full GDPR-style deletion with 30-day grace period, data export, and anonymization of ratings.
- **Dispute resolution:** None. The rating system is the sole accountability mechanism.
- **Inactivity:** Email warning at 1 month, final warning at 2 months, auto-delist (but keep in account) at 3 months. Re-list automatically on next login.
- **Match limits:** New users get 1 active match. Capacity grows with ratings received: `min(max(rating_count, 1), 10)`.
- **Trade auto-close:** Weekly rating reminders after trade confirmation. After 3 weeks with no rating, trade is auto-closed and book is assumed received.
