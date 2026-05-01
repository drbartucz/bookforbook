# BookForBook: Agent Mandates & Standards

This file contains foundational mandates for the Gemini CLI agent. These instructions take absolute precedence over general defaults.

## Project Context
BookForBook is a peer-to-peer book swapping platform where users trade physical books via shipping.

- **Backend:** Django (Python 3.12+) with Django Rest Framework.
- **Frontend:** React 18+ (Vite, JavaScript), CSS Modules, TanStack React Query, Radix UI.
- **Database:** PostgreSQL (Production), SQLite (Local/Test).

## Essential Commands

### Backend
```bash
# Run dev server
python manage.py runserver

# Run background task worker (Django-Q2)
python manage.py qcluster

# Run all tests
pytest

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Seed development data
python scripts/seed_data.py
```

### Frontend
```bash
cd frontend
npm run dev          # Vite dev server
npm run test:run     # Vitest single run
npm run e2e          # Playwright critical tests
```

## Architecture & Logic

### App Responsibilities
| App | Responsibility |
|-----|---------------|
| `accounts` | Custom `User`, JWT, USPS address verification (encrypted), inactivity tracking. |
| `books` | ISBN cache (ISBN-13 normalized) via Open Library API. |
| `inventory` | `UserBook` (have-list) and `WishlistItem` (want-list). |
| `matching` | Direct match and 3-5 user ring detection. |
| `trading` | Proposals, trades, shipments, and lifecycle management. |
| `donations` | One-directional donations to libraries/bookstores. |
| `ratings` | 1–5 star ratings; rolling average of last 10. |
| `notifications` | Email and in-app alerts (Django-Q2). |
| `messaging` | Structured trade messages. |
| `backups` | Database backups to Backblaze B2. |

### Core Rules
1. **Business Logic:** Must reside in `services/`, NOT in views or serializers.
2. **UUIDs:** All models must use UUID primary keys.
3. **Address Privacy:** Address fields are encrypted and only revealed to confirmed trade partners.
4. **Matching:** Automatic matching excludes institutional users. Direct matches and Rings (3-5 users) are the primary trade triggers.
5. **Institutional Users:** Libraries/bookstores require `is_verified=True` and participate via manual proposals or donations.

## Engineering Standards
- **Styling:** Use **Vanilla CSS with CSS Modules** (`.module.css`).
- **Data Fetching:** Use `useQuery` and `useMutation` from `@tanstack/react-query`.
- **Validation:** Always verify `EmailVerifiedPermission` and `user_has_verified_shipping_address`.
- **Testing:** Every new feature MUST have a corresponding test file.

## Workflow
- **Surgical Edits:** Use the `replace` tool for targeted changes.
- **Verification:** Run `pytest` after backend changes.
- **Git:** Work in feature branches (e.g., `feat/`, `fix/`).
