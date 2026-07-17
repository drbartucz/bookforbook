# Credit System — Change Plan

**Status:** Proposed (not yet implemented)
**Author:** design discussion, 2026-07-17
**Branch:** `claude/credit-system-book-trades-7dgnkz`

---

## 1. Goal

Increase sign-up conversion and trade activity by removing the chicken-and-egg
requirement that a *mutual* match must exist before anyone can trade. Introduce a
**credit** — an IOU worth exactly one book — so a user can send a book now to earn
the right to receive one later, or spend an existing credit to request a book,
without waiting for the matcher to find a two-way barter.

---

## 2. Core model (locked decisions)

A credit is **an IOU for one book — never a fraction, never a price**. The system
is a **closed transfer economy**, not money.

| Rule | Decision |
|------|----------|
| Starting balance | Every individual starts with **5** credits (one-time grant at signup) |
| Denomination | Whole credits only — always "book for book", no partial/variable cost |
| Maximum balance | **10** (credits earned above the cap are simply not granted) |
| Expiry | None |
| Earn trigger | **Delivery confirmation** (receiver marks the book received) |
| Cancel before delivery | **Nothing happens** — no credit moves |
| Institutions | **Never earn** credits; have **infinite** credits to disperse |
| Donations (→ institution) | Donor **earns +1** credit on delivery |
| Gifts (individual → individual) | **No** credit earned or spent |

**Accounting invariant:** every book that moves between two individuals is
`sender +1 / receiver −1` (net zero). New credits are *minted* only when a user
donates to an institution. Credits *leave* the system only via the max-10 cap.
This keeps user-to-user trading zero-sum, so credits cannot inflate to worthless.

### Resolved design decisions

1. **Overspend guard** — require the credit-spending party (the book *receiver*)
   to have **≥1 available credit at acceptance**, and treat accepted-but-not-yet-
   delivered credit trades as **open commitments** so a user cannot accept more
   incoming credit-books than they can pay for. The credit still only *moves* at
   delivery, so a cancellation before delivery leaves balances untouched.
   `available = credit_balance − open_credit_commitments`.
2. **Match vs. credit path** — a credit proposal may target **anyone listing the
   book**; it is a standalone path parallel to auto-matching, not gated on the
   matcher being unable to solve it.
3. **Institutions as targets** — a user **need not** spend a credit to receive an
   institution's book: the institution disperses from its infinite pool and the
   receiving user pays **nothing** (free-book faucet).

---

## 3. Credit settlement matrix

Applied at **trade completion** (all shipments received), per book move:

| Trade source | Sender | Receiver | Sender credit | Receiver credit |
|--------------|--------|----------|---------------|-----------------|
| Proposal, `payment_type=credit` | individual | individual | **+1** (cap 10) | **−1** |
| Proposal, `payment_type=credit` | institution | individual | none (inst. never earns) | **none** (institution covers it — free) |
| Proposal, `payment_type=credit` | individual | institution | **+1** (cap 10) | none (infinite) |
| Proposal, `payment_type=match` (barter) | any | any | none | none |
| Match (auto-matched barter) | any | any | none | none |
| Donation (→ institution) | individual | institution | **+1** (cap 10) | none |
| Gift (individual → individual) | individual | individual | none | none |

Note: the donation-vs-gift distinction is `donation.recipient.is_institutional`
(no dedicated field exists on `Donation`).

---

## 4. Data model changes

### 4.1 `apps/accounts/models.py` — `User`

Add alongside the existing denormalized stats (`total_trades`, etc.):

```python
credit_balance = models.PositiveSmallIntegerField(default=5)

MAX_CREDITS = 10

@property
def has_infinite_credits(self) -> bool:
    return self.is_institutional
```

`credit_balance` is a **denormalized cache**; the `CreditTransaction` ledger
(below) is the source of truth. Institutions ignore `credit_balance` entirely.

### 4.2 New app `apps/credits/`

Follows the standard app layout (`models.py`, `serializers.py`, `views.py`,
`urls.py`, `services/`, `tests/`). Register in `INSTALLED_APPS`.

```python
# apps/credits/models.py
class CreditTransaction(models.Model):
    class Reason(models.TextChoices):
        SIGNUP_GRANT   = "signup_grant",  "Signup grant"
        TRADE_SENT     = "trade_sent",    "Book sent (credit earned)"
        TRADE_RECEIVED = "trade_received","Book received (credit spent)"
        DONATION       = "donation",      "Donation to institution"

    id = UUIDField(primary_key=True, default=uuid4, editable=False)
    user = FK(User, related_name="credit_transactions")
    delta = SmallIntegerField()          # +1 or -1
    reason = CharField(choices=Reason.choices)
    balance_after = PositiveSmallIntegerField()   # snapshot for audit
    trade = FK("trading.Trade", null=True, blank=True, on_delete=SET_NULL)
    donation = FK("donations.Donation", null=True, blank=True, on_delete=SET_NULL)
    created_at = DateTimeField(auto_now_add=True)
```

### 4.3 `apps/trading/models.py` — `TradeProposal`

Add a payment type so barter and credit proposals share one model:

```python
class PaymentType(models.TextChoices):
    MATCH  = "match",  "Barter (book for book)"
    CREDIT = "credit", "Credit (one-directional)"

payment_type = models.CharField(
    max_length=10, choices=PaymentType.choices, default=PaymentType.MATCH
)
```

A `credit` proposal carries **exactly one** `TradeProposalItem` (one book, one
direction); a `match` proposal carries two (one in each direction, as today).

### 4.4 Migrations

- `accounts`: add `credit_balance`; **data migration** to backfill existing
  individual users to `5` (or leave at default — decide, see §9).
- `credits`: create `CreditTransaction`.
- `trading`: add `payment_type` (default `match`, so existing rows are unaffected).

---

## 5. Service layer

### 5.1 `apps/credits/services/ledger.py`

The only place that mutates `credit_balance`. Every mutation writes a
`CreditTransaction`, under `select_for_update` on the user row, with `F()` updates.

```python
def grant(user, reason, *, trade=None, donation=None) -> bool:
    """+1, respecting MAX_CREDITS. No-op for institutions. Returns True if granted."""

def spend(user, reason, *, trade=None, donation=None) -> None:
    """-1. No-op for institutions (infinite). Raises InsufficientCredits if <1."""

def available_credits(user) -> int | None:
    """None for institutions (infinite); else credit_balance − open_commitments."""

def open_commitments(user) -> int:
    """Count of accepted-not-delivered credit trades where `user` is the receiver."""
```

`open_commitments` is **computed** (a query over `Trade` joined to credit
proposals in status `confirmed|shipping|one_received` where the user is the
shipment receiver) rather than a stored counter — avoids drift, keeps it "book
for book" with no extra bookkeeping field.

### 5.2 `apps/credits/services/settlement.py`

```python
def settle_trade_credits(trade) -> None:
    """Apply the §3 matrix for a just-completed trade. Idempotent."""
```

Idempotency: guard on whether `CreditTransaction`s already exist for this trade
(the completion path is already concurrency-guarded via `select_for_update` on
the trade row in `check_trade_completion`).

---

## 6. Integration points (existing code)

| File | Change |
|------|--------|
| `apps/accounts/…` (signup) | Grant is implicit via `credit_balance` default = 5; optionally write a `signup_grant` `CreditTransaction` for a complete ledger. |
| `apps/trading/services/trade_workflow.py::check_trade_completion` | After marking the trade `COMPLETED`, call `settle_trade_credits(trade)`. Single choke point that covers match, proposal, **and** donation trades. |
| `apps/trading/services/trade_workflow.py::create_trade_from_proposal` | Branch on `proposal.payment_type`: `credit` → expect **1** item, create one shipment; `match` → existing 2-item path unchanged. |
| Proposal **accept** view/service | For `payment_type=credit`, before creating the trade: verify the book-receiving party has `available_credits ≥ 1` (skip if institution). Reject with a clear error otherwise. Runs inside the same atomic block that locks the trade. |
| `apps/donations/views.py` | No credit logic here — donation credits are granted at trade completion via `settle_trade_credits`, since donations already become `source_type=DONATION` trades. |

**Why completion, not acceptance:** honors "earn on delivery" and "cancel before
delivery = nothing happens" for free — no credit has moved until the receiver
confirms.

---

## 7. API changes

- **User profile** (`UserMeSerializer`, `UserPublicProfileSerializer` as
  appropriate): add `credit_balance` and a computed `credits_available`
  (and an `unlimited_credits: true` flag for institutions).
- **Proposal create serializer**: accept `payment_type`; validate item count
  (1 for credit, 2 for match) and that a credit proposal's item direction is
  coherent. Apply `EmailVerifiedPermission` and the shipping-address check as
  usual.
- **New** `GET /api/v1/credits/transactions/` — paginated ledger for the current
  user (`EmailVerifiedPermission`). Read-only.
- Proposal-accept error: `409/400` with `code: "insufficient_credits"` when the
  receiver cannot afford it.

---

## 8. Frontend changes (`frontend/`)

- Credit balance chip in the nav / profile header (show "∞" for institutions).
- Proposal composer: a payment-type toggle (Barter / Use a credit / Offer for a
  credit); credit mode collapses to a single-book selection.
- Confirmation copy on credit proposals ("You'll spend 1 credit when you confirm
  the book arrived" / "You'll earn 1 credit when they confirm arrival").
- Credit history view backed by the new transactions endpoint.
- Disable the "use a credit" option when `credits_available < 1` with an
  explanatory tooltip.
- Vanilla CSS modules only (per repo convention).

---

## 9. Open follow-ups / risks

- **Backfill decision:** grant existing users the 5-credit starting balance, or
  start them at 0 and only new signups get 5? (Leaning: give existing individuals
  5 to seed activity.)
- **Cap side effect:** a user sitting at 10 credits earns nothing for donating,
  mildly disincentivizing the exact behavior we want. Acceptable at launch; the
  cap is a one-line constant to raise later.
- **Low-quality dumping:** with no condition-based pricing, users may farm credits
  by shipping junk. Mitigations deferred (e.g., ratings already gate reputation);
  revisit if observed.
- **Reserve integrity:** `open_commitments` is computed per check; verify the
  query is correct under the exact set of "in-flight" trade statuses.

---

## 10. Test plan

`apps/credits/tests/`:
- `grant` respects `MAX_CREDITS`; excess silently not granted.
- `spend` raises `InsufficientCredits` at 0; is a no-op for institutions.
- `available_credits` subtracts open commitments; `None` for institutions.
- `settle_trade_credits` for each row of the §3 matrix (incl. gift = no-op,
  donation→institution = donor +1, institution sender = free to receiver).
- Idempotency: calling settlement twice yields one set of transactions.

`apps/trading/tests/`:
- Credit proposal (1 item) create → accept (balance check) → ship → receive →
  credits move exactly once.
- Accept → cancel before delivery → **no** credit movement.
- Concurrent acceptance guard: user with 1 credit cannot commit to 2 incoming
  credit books.
- Barter (`payment_type=match`) path unchanged, moves no credits.

Coverage threshold is 70% (repo standard); run `pytest`.

---

## 11. Rollout order

1. `accounts` migration (`credit_balance`) + backfill.
2. `credits` app (model, ledger, settlement, tests) — no wiring yet.
3. `trading`: `payment_type`, proposal create/accept branching, completion hook.
4. `donations`: covered by completion hook (verify, no new code).
5. API serializers + transactions endpoint.
6. Frontend.
7. Full `pytest` + `npm run test:run`.
