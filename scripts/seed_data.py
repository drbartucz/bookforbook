#!/usr/bin/env python
"""
Development seed wrapper for BookForBook.

This script delegates to the management command:
    python manage.py seed_data [--size small|medium|large] [--seed 42] [--reset]

Run with:
    python scripts/seed_data.py
"""
import os
import sys


def main() -> None:
    # Add project root to Python path.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

    import django

    django.setup()

    from django.core.management import call_command

    call_command("seed_data", *sys.argv[1:])


if __name__ == "__main__":
    main()
