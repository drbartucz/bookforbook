#!/bin/bash

# Exit on any error
set -e

# Check for Railway CLI
if ! command -v railway &> /dev/null; then
    echo "Error: railway CLI is not installed. Please install it from https://docs.railway.app/guides/cli"
    exit 1
fi

# Ensure we are logged in and linked
if ! railway status &> /dev/null; then
    echo "Error: Not logged into Railway or project not linked. Run 'railway login' and 'railway link'."
    exit 1
fi

TEMP_DUMP="prod_dump.json"

echo "Step 1: Dumping production data from Railway..."
# Exclude contenttypes and permissions to avoid IntegrityErrors during loaddata
# Exclude sessions and admin log entries to keep the dump clean
railway run python manage.py dumpdata \
    --exclude contenttypes \
    --exclude auth.permission \
    --exclude sessions \
    --exclude admin.logentry \
    --indent 2 > "$TEMP_DUMP"

echo "Step 2: Flushing local database..."
python manage.py flush --no-input

echo "Step 3: Loading production data into local database..."
python manage.py loaddata "$TEMP_DUMP"

echo "Step 4: Cleaning up..."
rm "$TEMP_DUMP"

echo "Done! Production data has been synced to your local database."
