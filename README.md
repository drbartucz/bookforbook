# BookForBook

**Trade books, not money.** BookForBook is a free platform for people in the continental USA to swap books 1-for-1. No payments, no credits — just books changing hands between people who want them.

---

## Table of Contents

- [How It Works](#how-it-works)
- [For the General Public — Browsing Without an Account](#for-the-general-public--browsing-without-an-account)
- [For Individual Traders](#for-individual-traders)
  - [Getting Started](#getting-started-as-a-trader)
  - [Listing Books You Want to Give Away](#listing-books-you-want-to-give-away)
  - [Building Your Want List](#building-your-want-list)
  - [When a Match is Found](#when-a-match-is-found)
  - [Exchange Rings (Multi-Party Trades)](#exchange-rings-multi-party-trades)
  - [Proposing a Trade Directly](#proposing-a-trade-directly)
  - [Shipping Your Book](#shipping-your-book)
  - [Leaving a Rating](#leaving-a-rating)
  - [Your Profile and Reputation](#your-profile-and-reputation)
  - [Account Inactivity](#account-inactivity)
  - [Deleting Your Account](#deleting-your-account)
- [For Libraries and Bookstores](#for-libraries-and-bookstores)
  - [Getting Approved](#getting-approved)
  - [Managing Your Wanted List](#managing-your-wanted-list)
  - [Receiving Donations](#receiving-donations)
- [Key Rules](#key-rules)
- [FAQ](#faq)

---

## How It Works

1. You list books you want to give away (by ISBN) and rate their condition
2. You add books to your want list
3. The system scans for matches — either direct (you have what someone else wants, and they have what you want) or rings (a chain of 3–5 people who can all trade with each other)
4. When a match is found, all parties are notified and must confirm
5. Once everyone confirms, shipping addresses are revealed
6. You ship your book via USPS Media Mail, mark it sent, then mark it received when it arrives
7. Leave a rating — your reputation on the platform is built from your last 10 ratings

---

## For the General Public — Browsing Without an Account

You do not need an account to browse available books.

**What you can do without signing up:**
- Browse all books currently available for trade at `/api/v1/browse/available/`
- Search by title, author, or ISBN: `/api/v1/browse/available/?q=tolkien`
- Filter by condition: `/api/v1/browse/available/?condition=like_new`
- View public profiles of traders at `/api/v1/users/{user_id}/`
- View a trader's ratings at `/api/v1/users/{user_id}/ratings/`
- Browse verified libraries and bookstores at `/api/v1/institutions/`
- See what a specific institution is looking for at `/api/v1/institutions/{id}/wanted/`
- Get a shipping cost estimate for any listed book at `/api/v1/browse/shipping-estimate/{book_id}/`

**What requires an account:**
- Listing books, adding to your want list, accepting matches, and trading

---

## For Individual Traders

### Getting Started as a Trader

**1. Register**

```
POST /api/v1/auth/register/
{
  "username": "yourname",
  "email": "you@example.com",
  "password": "yourpassword"
}
```

You will receive a verification email. You must verify your email before you can list books or trade.

**2. Verify your email**

Click the link in the verification email, or submit the token directly:

```
POST /api/v1/auth/verify-email/
{
  "uid": "...",
  "token": "..."
}
```

**3. Log in**

```
POST /api/v1/auth/login/
{
  "email": "you@example.com",
  "password": "yourpassword"
}
```

Returns `access` and `refresh` JWT tokens. Include the access token in all subsequent requests:

```
Authorization: Bearer <access_token>
```

**4. Complete your profile**

Add your shipping address — this is required before any trade can be confirmed. Your address is encrypted and only revealed to confirmed trade partners.

```
PATCH /api/v1/users/me/
{
  "full_name": "Jane Smith",
  "address_line_1": "123 Main St",
  "city": "Portland",
  "state": "OR",
  "zip_code": "97201"
}
```

Only continental US states are accepted.

---

### Listing Books You Want to Give Away

Add a book to your have-list by ISBN. The system looks up the title, author, and cover from Open Library automatically.

```
POST /api/v1/my-books/
{
  "isbn": "9780261103573",
  "condition": "very_good"
}
```

Condition options: `like_new`, `very_good`, `good`, `acceptable`

**View your have-list:**
```
GET /api/v1/my-books/
```

**Update a book's condition:**
```
PATCH /api/v1/my-books/{id}/
{
  "condition": "good"
}
```

**Remove a book** (only if not currently reserved or in a trade):
```
DELETE /api/v1/my-books/{id}/
```

You can list multiple copies of the same ISBN — each is tracked separately.

---

### Building Your Want List

```
POST /api/v1/wishlist/
{
  "isbn": "9780743273565",
  "min_condition": "good"
}
```

`min_condition` sets the lowest condition you'll accept. The system will only match you with books that meet this threshold.

**View your want list:**
```
GET /api/v1/wishlist/
```

**Update minimum condition:**
```
PATCH /api/v1/wishlist/{id}/
{
  "min_condition": "very_good"
}
```

**Remove a want:**
```
DELETE /api/v1/wishlist/{id}/
```

---

### When a Match is Found

The matching engine runs automatically every 6 hours and whenever you add a new book or want. When a match is found:

1. You receive an email notification and an in-app notification
2. Log in and view your matches: `GET /api/v1/matches/`
3. Review the match details — who you're trading with, which book you're giving, which you're getting
4. **Accept:** `POST /api/v1/matches/{id}/accept/`
5. **Decline:** `POST /api/v1/matches/{id}/decline/`

A match only proceeds if **all** parties accept. If anyone declines, the match is cancelled and the books return to available status.

Once all parties accept, the trade is confirmed and shipping addresses are revealed automatically.

**New users start with 1 active match slot.** This grows up to 10 as you accumulate ratings.

---

### Exchange Rings (Multi-Party Trades)

Sometimes a direct swap isn't possible, but a chain works: Alice has what Bob wants, Bob has what Carol wants, Carol has what Alice wants. The system detects these cycles automatically (up to 5 people).

Ring trades work the same as direct trades — everyone must accept, everyone ships to the next person in the ring. If one person declines, the system attempts to reform the ring with other users before cancelling.

---

### Proposing a Trade Directly

If you see a book you want listed by another user (visible in browse), you can propose a trade directly without waiting for the matching engine.

```
POST /api/v1/proposals/
{
  "recipient_id": "user-uuid",
  "items": [
    {
      "user_book_id": "their-book-uuid",
      "direction": "recipient_sends"
    },
    {
      "user_book_id": "your-book-uuid",
      "direction": "proposer_sends"
    }
  ]
}
```

Proposals are always 1-for-1. The recipient can accept, decline, or counter-offer. You can counter their counter-offer. A trade is created when one party accepts.

**View your proposals:**
```
GET /api/v1/proposals/
```

---

### Shipping Your Book

Once a trade is confirmed, view your trade details including the recipient's shipping address:

```
GET /api/v1/trades/{id}/
```

Ship via **USPS Media Mail** — the cheapest option for books (typically $4–6 for the first pound). Keep your tracking number.

**Mark as shipped:**
```
POST /api/v1/trades/{id}/mark-shipped/
{
  "shipment_id": "shipment-uuid",
  "tracking_number": "9400111899223456789012",
  "shipping_method": "USPS Media Mail"
}
```

**When your book arrives, mark it received:**
```
POST /api/v1/trades/{id}/mark-received/
{
  "shipment_id": "shipment-uuid"
}
```

Once both shipments are marked received, the trade is complete.

---

### Leaving a Rating

After a trade completes you can rate the other person (1–5 stars):

```
POST /api/v1/trades/{id}/rate/
{
  "score": 5,
  "book_condition_accurate": true,
  "comment": "Book was exactly as described. Fast shipping!"
}
```

- Ratings are based on your last 10 received — your score reflects recent behavior
- Rating reminders are sent weekly for up to 3 weeks
- Trades auto-close after 3 weeks with no rating (books marked traded, no score recorded)

---

### Your Profile and Reputation

```
GET /api/v1/users/me/
```

Your public profile (visible to anyone):
```
GET /api/v1/users/{id}/
```

Your ratings:
```
GET /api/v1/users/{id}/ratings/
```

**Export your data** (GDPR):
```
GET /api/v1/users/me/export/
```

---

### Account Inactivity

If you don't log in:
- **After 1 month:** warning email
- **After 2 months:** second warning
- **After 3 months:** your books are hidden from matching (but not deleted)

Log back in at any time to automatically restore your books and resume matching.

---

### Deleting Your Account

```
DELETE /api/v1/users/me/
{
  "password": "yourpassword"
}
```

Your data export is emailed to you. Active matches and proposals are cancelled. Account is deactivated immediately (30-day grace period before full deletion).

---

## For Libraries and Bookstores

Libraries and bookstores participate differently from individual traders — they **receive donations only**. They do not trade or ship books out.

### Getting Approved

1. Register with `account_type` set to `library` or `bookstore`:

```
POST /api/v1/auth/register/
{
  "username": "portland_public_library",
  "email": "books@portlandlibrary.org",
  "password": "yourpassword",
  "account_type": "library",
  "institution_name": "Portland Public Library"
}
```

2. Your account is created but **inactive** until a platform administrator approves it via the admin panel. You will receive an email when approved.

3. Verify your email address (same as individual users).

### Managing Your Wanted List

Once approved, build a list of books your institution is looking for. This list is public.

```
POST /api/v1/wishlist/
{
  "isbn": "9780525559474",
  "min_condition": "acceptable"
}
```

View your institution's public wanted list (visible to anyone without login):
```
GET /api/v1/institutions/{id}/wanted/
```

### Receiving Donations

Individual users can offer a donation directly to your institution:

```
POST /api/v1/donations/
{
  "institution_id": "library-uuid",
  "user_book_id": "book-uuid"
}
```

You review incoming donation offers:
```
GET /api/v1/donations/
```

**Accept:**
```
POST /api/v1/donations/{id}/accept/
```

**Decline:**
```
POST /api/v1/donations/{id}/decline/
```

Once accepted, the donor ships the book to your institution. No address reveal is needed on your end — the donor sees your institution's public address.

---

## Key Rules

| Rule | Detail |
|------|--------|
| 1-for-1 only | Every trade is exactly one book in each direction |
| Continental USA only | Shipping addresses must be in the 48 continental states (no Hawaii, Alaska, territories) |
| Email verification | Required before listing books, matching, or trading. Browsing is open to all. |
| Match capacity | New users: 1 active match slot. Grows to 10 with trading history. |
| Address privacy | Shipping addresses are encrypted and only revealed to confirmed trade partners |
| Ring size | Exchange rings are capped at 5 participants |
| Auto-close | Trades auto-close 3 weeks after confirmation if no ratings are submitted |
| Inactivity | Books hidden after 3 months inactive; restored on next login |
| No disputes | The rating system is the sole accountability mechanism. There is no dispute resolution. |
| Institutional accounts | Libraries and bookstores require admin approval and can only receive donations |

---

## FAQ

**Do I pay anything?**
No. The platform is free. You pay only your own shipping costs (typically $4–6 USPS Media Mail per book).

**What if the book I receive is not as described?**
Leave an honest rating. There is no formal dispute process — the rating system is how accountability works on this platform.

**Can I trade the same book twice?**
Yes. Add it to your have-list again after the first trade completes.

**What if the other person never ships?**
The trade auto-closes after 3 weeks. Their rating (or lack thereof) reflects this. You can leave a 1-star rating with a note.

**Can I be in multiple trades at once?**
Yes, up to your match capacity (1 slot for new users, up to 10 as you build history).

**What if I'm in a ring and someone declines?**
The system attempts to reform the ring without that person. If it can't, the ring is cancelled and all books return to available.

**How do I find a specific book?**
Browse: `GET /api/v1/browse/available/?q=great+gatsby`

**What condition ratings mean:**
- `like_new` — unread or near perfect
- `very_good` — minor signs of wear, no damage
- `good` — some wear, all pages intact
- `acceptable` — heavy wear, may have notes/highlighting, fully readable
