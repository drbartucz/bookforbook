# Superuser Guide — BookForBook

This document covers everything a platform administrator needs to manage BookForBook via the Django admin panel and command line.

---

## Table of Contents

- [Accessing the Admin Panel](#accessing-the-admin-panel)
- [Creating a Superuser](#creating-a-superuser)
- [Managing Users](#managing-users)
  - [Approving Institutional Accounts](#approving-institutional-accounts)
  - [Verifying a User's Email Manually](#verifying-a-users-email-manually)
  - [Suspending or Deactivating a User](#suspending-or-deactivating-a-user)
  - [Viewing a User's Books, Trades, and Ratings](#viewing-a-users-books-trades-and-ratings)
- [Managing Books](#managing-books)
- [Managing Matches and Trades](#managing-matches-and-trades)
- [Managing Donations](#managing-donations)
- [Background Tasks and Scheduling](#background-tasks-and-scheduling)
  - [Running Periodic Tasks Manually](#running-periodic-tasks-manually)
  - [Cron Schedule Reference](#cron-schedule-reference)
- [Monitoring and Maintenance](#monitoring-and-maintenance)
  - [Checking for Stuck Trades](#checking-for-stuck-trades)
  - [Manually Expiring Old Matches](#manually-expiring-old-matches)
  - [Triggering the Matching Engine](#triggering-the-matching-engine)
- [Database Access](#database-access)
- [Logs](#logs)
- [Security Tasks](#security-tasks)
  - [Rotating the Encryption Key](#rotating-the-encryption-key)
  - [Rotating the Secret Key](#rotating-the-secret-key)
- [GDPR and Data Deletion](#gdpr-and-data-deletion)
- [Deployment Tasks](#deployment-tasks)
  - [Applying Migrations](#applying-migrations)
  - [Collecting Static Files](#collecting-static-files)
  - [Restarting the Server](#restarting-the-server)

---

## Accessing the Admin Panel

The Django admin panel is available at:

```
https://yourdomain.com/admin/
```

Log in with your superuser credentials. From here you can manage all models in the system.

---

## Creating a Superuser

If no superuser exists yet (fresh install):

```bash
cd ~/private/bookforbook
source .venv/bin/activate
python manage.py createsuperuser
```

You will be prompted for a username, email, and password.

To create additional admin users without full superuser privileges, create a regular user via the admin panel and grant them `Staff status` plus the specific permissions they need.

---

## Managing Users

### Approving Institutional Accounts

Libraries and bookstores must be approved by an admin before they can participate.

**In the admin panel:**
1. Go to **Accounts → Users**
2. Filter by `account_type = library` or `account_type = bookstore`
3. Find accounts where `is_verified = False`
4. Open the user record
5. Check **Is verified** and save

Until `is_verified` is True, the institution will not appear in the public institutions directory and cannot receive donations.

**Things to verify before approving:**
- The institution name looks legitimate
- The email domain matches the institution
- They have a valid US address on file

---

### Verifying a User's Email Manually

If a user did not receive their verification email:

**In the admin panel:**
1. Go to **Accounts → Users**
2. Find the user
3. Check **Email verified** and set **Email verified at** to the current time
4. Save

---

### Suspending or Deactivating a User

**In the admin panel:**
1. Go to **Accounts → Users**
2. Find the user
3. Uncheck **Is active**
4. Save

Deactivated users cannot log in. Their books will no longer appear in matching. Any active matches they are part of should be manually cancelled (see below) or will expire naturally.

To re-activate: check **Is active** again.

---

### Viewing a User's Books, Trades, and Ratings

From a user's admin record, use the related object links at the bottom of the page to see:
- Their have-list (UserBooks)
- Their want-list (WishlistItems)
- Matches they are part of (via MatchLegs)
- Trades (via TradeShipments)
- Ratings given and received

---

## Managing Books

The **Books** model is a local cache of ISBN data from Open Library. You generally do not need to edit these directly.

**When to edit a Book record:**
- Open Library returned no data (title/author are blank) and you want to fill them in manually
- A title or author was cached incorrectly

**In the admin panel:** Go to **Books → Books**, search by ISBN or title, and edit the record.

Books are never deleted — they are cached permanently once looked up.

---

## Managing Matches and Trades

### Cancelling a Match

If a match needs to be manually cancelled (e.g. both users report a problem):

**In the admin panel:**
1. Go to **Matching → Matches**
2. Find the match
3. Change `status` to `expired`
4. Save

The associated UserBooks will remain `reserved` — you may need to manually set them back to `available` via **Inventory → User books**.

### Viewing All Active Trades

**In the admin panel:** Go to **Trading → Trades**, filter by status `confirmed`, `shipping`, or `one_received`.

### Manually Closing a Trade

If both parties confirm a trade is done but the system hasn't auto-closed it:

**In the admin panel:**
1. Go to **Trading → Trades**
2. Find the trade
3. Set `status` to `completed` and set `completed_at` to now
4. Save
5. Manually mark the associated UserBooks as `traded` via **Inventory → User books**

---

## Managing Donations

**In the admin panel:** Go to **Donations → Donations** to see all pending, accepted, and declined donations.

If a donation offer is stuck (neither accepted nor declined), you can manually set its status or delete the record.

---

## Background Tasks and Scheduling

Periodic tasks run via cron rather than a background worker (the hosting environment does not support background processes with shared memory).

### Running Periodic Tasks Manually

```bash
cd ~/private/bookforbook
source .venv/bin/activate

# Run a specific task
python manage.py run_periodic_tasks --task=matching
python manage.py run_periodic_tasks --task=expire_matches
python manage.py run_periodic_tasks --task=inactivity
python manage.py run_periodic_tasks --task=rating_reminders
python manage.py run_periodic_tasks --task=auto_close

# Run all tasks at once
python manage.py run_periodic_tasks --task=all
```

### Cron Schedule Reference

Edit the crontab with `crontab -e`. Replace the paths with your actual username and paths.

```
# Every 6 hours — full matching scan
0 */6 * * * /home/bookforbook/private/bookforbook/.venv/bin/python /home/bookforbook/private/bookforbook/manage.py run_periodic_tasks --task=matching >> /home/bookforbook/private/logs/cron.log 2>&1

# Every hour — expire old matches
0 * * * * /home/bookforbook/private/bookforbook/.venv/bin/python /home/bookforbook/private/bookforbook/manage.py run_periodic_tasks --task=expire_matches >> /home/bookforbook/private/logs/cron.log 2>&1

# Daily at 2am — inactivity check (warnings + auto-delist)
0 2 * * * /home/bookforbook/private/bookforbook/.venv/bin/python /home/bookforbook/private/bookforbook/manage.py run_periodic_tasks --task=inactivity >> /home/bookforbook/private/logs/cron.log 2>&1

# Weekly Sunday 3am — rating reminders
0 3 * * 0 /home/bookforbook/private/bookforbook/.venv/bin/python /home/bookforbook/private/bookforbook/manage.py run_periodic_tasks --task=rating_reminders >> /home/bookforbook/private/logs/cron.log 2>&1

# Weekly Sunday 3:15am — auto-close expired trades
15 3 * * 0 /home/bookforbook/private/bookforbook/.venv/bin/python /home/bookforbook/private/bookforbook/manage.py run_periodic_tasks --task=auto_close >> /home/bookforbook/private/logs/cron.log 2>&1
```

Create the log directory if it doesn't exist:
```bash
mkdir -p ~/logs
```

View cron output:
```bash
tail -f ~/logs/cron.log
```

---

## Monitoring and Maintenance

### Checking for Stuck Trades

Trades stuck in `confirmed` or `shipping` for more than 3 weeks should auto-close via cron. To check manually:

**In the admin panel:** Go to **Trading → Trades**, filter by status `confirmed` or `shipping`, and sort by `confirmed_at` ascending. Any trade older than 3 weeks should have been auto-closed — if not, run the task manually:

```bash
python manage.py run_periodic_tasks --task=auto_close
```

### Manually Expiring Old Matches

Matches in `pending` or `proposed` status that have passed their `expires_at` time will be cleaned up by the `expire_matches` cron task. To run immediately:

```bash
python manage.py run_periodic_tasks --task=expire_matches
```

### Triggering the Matching Engine

To run the full matching scan immediately (e.g. after importing a batch of books):

```bash
python manage.py run_periodic_tasks --task=matching
```

---

## Database Access

Connect directly to the PostgreSQL database:

```bash
source ~/apps/postgres1/home/.bashrc
psql bookforbook
```

Useful queries:

```sql
-- Count users by account type
SELECT account_type, COUNT(*) FROM accounts_user GROUP BY account_type;

-- All pending matches
SELECT id, match_type, status, detected_at FROM matching_match WHERE status IN ('pending', 'proposed');

-- All active trades
SELECT id, status, confirmed_at, auto_close_at FROM trading_trade WHERE status NOT IN ('completed', 'auto_closed', 'cancelled');

-- Users with books delisted due to inactivity
SELECT username, email, books_delisted_at FROM accounts_user WHERE books_delisted_at IS NOT NULL;

-- Institutions pending approval
SELECT username, email, institution_name, account_type FROM accounts_user
WHERE account_type IN ('library', 'bookstore') AND is_verified = false;
```

---

## Logs

Django logs go to stdout by default. If running via gunicorn or a process manager, redirect output to a file.

To add file-based logging, add to your `.env` or `production.py`:

```python
LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': '/home/bookforbook/private/logs/django.log',
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'INFO',
    },
}
```

---

## Security Tasks

### Rotating the Encryption Key

Address fields are encrypted with `FIELD_ENCRYPTION_KEY`. **Rotating this key requires re-encrypting all address data** — do not simply change it in `.env` or existing data will become unreadable.

To rotate:
1. Add the new key as a secondary key (consult `django-encrypted-model-fields` docs for multi-key rotation)
2. Run a migration script that reads and re-saves each user record
3. Remove the old key

Contact the project maintainer before attempting this.

### Rotating the Secret Key

`SECRET_KEY` is used for JWT signing. Rotating it **immediately invalidates all existing JWT tokens** — all users will be logged out.

To rotate:
1. Generate a new key: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`
2. Update `SECRET_KEY` in `.env`
3. Restart the server

---

## GDPR and Data Deletion

### Exporting a User's Data

Users can export their own data via `GET /api/v1/users/me/export/`. As an admin you can retrieve the same data from the admin panel or via the shell:

```bash
python manage.py shell
```
```python
from apps.accounts.views import _build_user_export
from apps.accounts.models import User
user = User.objects.get(email='user@example.com')
import json
print(json.dumps(_build_user_export(user), indent=2, default=str))
```

### Deleting a User's Data

When a user requests deletion via the API, their account is deactivated immediately. Full anonymization (keeping rating scores but removing the user reference) should be performed after the 30-day grace period.

To fully delete a user from the admin panel:
1. Go to **Accounts → Users**
2. Find the user
3. Use the **Delete** action

This cascades to their UserBooks, WishlistItems, and TradeProposal records. Ratings where they are the `rater` will lose the user reference (set to null or anonymized depending on your schema).

---

## Deployment Tasks

### Applying Migrations

After pulling new code:

```bash
cd ~/private/bookforbook
source .venv/bin/activate
git pull origin main
pip install -r requirements.txt
python manage.py migrate
```

### Collecting Static Files

```bash
python manage.py collectstatic --noinput
```

### Restarting the Server

If running via gunicorn with a process manager, send a HUP signal to reload:

```bash
kill -HUP $(cat /tmp/gunicorn.pid)
```

Or if using a simpler setup, stop and restart the process manually.
