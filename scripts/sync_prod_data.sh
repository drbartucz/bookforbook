#!/bin/bash

# Exit on any error
set -e

# Ensure we are in the project root
cd "$(dirname "$0")/.."

# Check for required tools
for cmd in railway jq; do
    if ! command -v $cmd &> /dev/null; then
        echo "Error: $cmd is not installed."
        exit 1
    fi
done

# Load local DATABASE_URL from .env
if [ -f .env ]; then
    DATABASE_URL=$(grep "^DATABASE_URL=" .env | cut -d'=' -f2- | sed "s/^'//;s/'$//;s/^\"//;s/\"$//")
    DATABASE_PUBLIC_URL_HOST=$(grep "^DATABASE_PUBLIC_URL=" .env | cut -d'=' -f2- | sed "s/^'//;s/'$//;s/^\"//;s/\"$//")
else
    echo "Error: .env file not found."
    exit 1
fi

if [ -z "$DATABASE_URL" ]; then
    echo "Error: DATABASE_URL not found in .env."
    exit 1
fi

# Determine Python command
if [ -f ".venv/bin/python" ]; then
    PYTHON_CMD=".venv/bin/python"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

echo "Step 1: Determining production database URL..."
# Fetch internal DATABASE_URL from Railway to get credentials
INTERNAL_URL=$(railway variables --json | jq -r '.DATABASE_URL')
if [ -z "$INTERNAL_URL" ] || [ "$INTERNAL_URL" == "null" ]; then
    echo "Error: Could not fetch DATABASE_URL from Railway."
    exit 1
fi

# Extract components from internal URL: postgresql://user:pass@host:port/db
PROTO=$(echo "$INTERNAL_URL" | grep :// | sed -e's,^\(.*://\).*,\1,g')
USER_PASS=$(echo "${INTERNAL_URL/$PROTO/}" | grep @ | cut -d@ -f1)
DB_NAME=$(echo "$INTERNAL_URL" | grep / | cut -d/ -f4-)

if [ -n "$DATABASE_PUBLIC_URL_HOST" ]; then
    echo "Using DATABASE_PUBLIC_URL host from .env with Railway credentials"
    PROD_DB_URL="${PROTO}${USER_PASS}@${DATABASE_PUBLIC_URL_HOST}/${DB_NAME}"
else
    echo "Fetching public URL from Railway..."
    # If Railway has a public variable, use it, otherwise we're stuck
    RAIL_PUBLIC=$(railway variables --json | jq -r '.DATABASE_PUBLIC_URL // empty')
    if [ -n "$RAIL_PUBLIC" ]; then
        PROD_DB_URL="$RAIL_PUBLIC"
    else
        echo "Error: No public database URL found. Please add DATABASE_PUBLIC_URL to .env"
        exit 1
    fi
fi

echo "Step 2: Syncing data (this will wipe your local database)..."
read -p "Are you sure you want to continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

TEMP_DUMP="prod_dump.sql"

echo "Step 3: Attempting fast sync with pg_dump..."
if command -v pg_dump &> /dev/null; then
    if pg_dump "$PROD_DB_URL" --clean --no-owner --no-privileges -f "$TEMP_DUMP" 2>/tmp/pg_error; then
        echo "Restoring to local database..."
        psql "$DATABASE_URL" -f "$TEMP_DUMP" > /dev/null
        rm "$TEMP_DUMP"
        echo "Done! Data synced via pg_dump."
        exit 0
    else
        echo "pg_dump failed (likely version mismatch)."
        cat /tmp/pg_error
        echo "Falling back to Django dumpdata (slower)..."
    fi
else
    echo "pg_dump not found. Using Django dumpdata..."
fi

# Fallback Method: Django dumpdata
echo "Step 4: Syncing via Django dumpdata..."
TEMP_JSON="prod_dump.json"

# We use the public URL for the remote command by temporarily overriding DATABASE_URL
DATABASE_URL="$PROD_DB_URL" $PYTHON_CMD manage.py dumpdata \
    --exclude contenttypes \
    --exclude auth.permission \
    --exclude sessions \
    --exclude admin.logentry \
    --indent 2 > "$TEMP_JSON"

echo "Flushing local database..."
$PYTHON_CMD manage.py flush --no-input

echo "Loading data..."
$PYTHON_CMD manage.py loaddata "$TEMP_JSON"
rm "$TEMP_JSON"

echo "Done! Production data has been synced to your local database."
