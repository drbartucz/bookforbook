# Architecture Design: Wishlist Gifting

## Overview
Wishlist Gifting extends the existing `Donation` system to allow peer-to-peer altruism. Users can browse public wishlists (or see demand for their own books) and send a book to a stranger with no expectation of return. This leverages the existing `TradeProposal` (source_type=donation) and `Trade` lifecycle.

## User Experience

### 1. Unified "My Books" (Have-list) Management
- The existing "My Books" page is enhanced to show community demand.
- **Demand Indicators:** Each book shows "X users want this" (Individuals) and/or "Wanted by Institutions".
- **Filtering/Sorting:** New options to filter by "Most Wanted" or "Wanted by Institutions" to help users prioritize gifting.
- **Actions:** Clicking a book opens its detail view, which now includes a "Gift / Donate" action if demand exists. Selecting this action opens the recipient selection list.

### 2. From Public Profiles
- When visiting a user's profile, the wishlist items are displayed.
- If the visitor owns a copy of a wishlist item, a "Gift this" button is shown.
- Clicking "Gift this" initiates the offer.

## Database Changes (`apps/donations`)

### Model: `Donation`
- **Rename Field:** `institution` (FK to User) → `recipient`.
- **Validation Rule:**
    - If `recipient.account_type` is `INDIVIDUAL`, the book *must* exist on the recipient's active wishlist.
    - If `recipient.account_type` is `LIBRARY` or `BOOKSTORE`, the gift is unrestricted.

## API Modifications

### 1. Donations API (`apps/donations`)
- **`DonationSerializer`**:
    - Rename `institution` to `recipient`.
    - Rename `institution_address` to `recipient_address`.
    - Update `get_recipient_address` to reveal address only after the recipient accepts the gift.
- **`DonationCreateSerializer`**:
    - Rename `institution_id` to `recipient_id`.
    - Add validation to check for a matching `WishlistItem` if the recipient is an individual.

### 2. Inventory API (`apps/inventory`)
- **`UserBookSerializer`**:
    - Add `want_count`: Number of active users who have this book on their wishlist.
    - Add `is_institution_wanted`: Boolean indicating if at least one verified institution wants this book.
- **`UserBookListView` / `inventory/me/` endpoint**:
    - Support new `sort_by=demand` and `filter_by=wanted` parameters to power the "My Books" enhancements.
- **New Endpoint:** `GET /api/v1/inventory/books/<uuid:book_id>/wanted-by/`
    - Returns a list of potential recipients (Individuals with the book on their wishlist AND verified Institutions).
- **`WishlistItemSerializer`**:
    - Add `viewer_can_gift`: Boolean indicating if the authenticated user has an `AVAILABLE` `UserBook` for this item.

## Lifecycle & Transitions

1. **Offer:** Donor creates a `Donation` (status: `OFFERED`).
2. **Acceptance:** Recipient accepts (status: `ACCEPTED`).
3. **Trade Creation:** A `Trade` record is automatically created with `source_type='donation'`.
4. **Fulfillment:** Standard trade shipping/receiving lifecycle follows.

## Notifications
- **Offer Received:** "A user would like to gift/donate [Book Title] to you!"
- **Offer Accepted:** "[Recipient Name] has accepted your gift of [Book Title]. Shipping address is now available."

## Security & Privacy
- **Address Privacy:** Recipient's shipping address is encrypted and only revealed to the donor *after* the recipient accepts the offer.
- **Donor Privacy:** While the recipient sees the donor's username in the system, the donor's return address will be visible on the physical shipping package.
