#!/usr/bin/env python
"""
Development seed script for BookForBook.

Run with: python scripts/seed_data.py
(from the project root with the virtual environment activated)
"""
import os
import sys

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django
django.setup()

from apps.accounts.models import User
from apps.books.models import Book
from apps.inventory.models import UserBook, WishlistItem


def create_test_users():
    """Create a set of test users for development."""
    users_data = [
        {
            'email': 'alice@example.com',
            'username': 'alice',
            'password': 'testpassword123',
            'full_name': 'Alice Smith',
            'address_line_1': '123 Main St',
            'city': 'Portland',
            'state': 'OR',
            'zip_code': '97201',
        },
        {
            'email': 'bob@example.com',
            'username': 'bob',
            'password': 'testpassword123',
            'full_name': 'Bob Jones',
            'address_line_1': '456 Oak Ave',
            'city': 'Seattle',
            'state': 'WA',
            'zip_code': '98101',
        },
        {
            'email': 'carol@example.com',
            'username': 'carol',
            'password': 'testpassword123',
            'full_name': 'Carol Williams',
            'address_line_1': '789 Pine Rd',
            'city': 'Denver',
            'state': 'CO',
            'zip_code': '80201',
        },
        {
            'email': 'portlandlibrary@example.com',
            'username': 'portlandpubliclibrary',
            'password': 'testpassword123',
            'account_type': 'library',
            'institution_name': 'Portland Public Library',
            'institution_url': 'https://multcolib.org',
            'city': 'Portland',
            'state': 'OR',
            'zip_code': '97201',
        },
    ]

    created_users = []
    for data in users_data:
        account_type = data.pop('account_type', 'individual')
        password = data.pop('password')
        try:
            user = User.objects.get(email=data['email'])
            print(f'User {data["email"]} already exists, skipping.')
        except User.DoesNotExist:
            user = User.objects.create_user(
                password=password,
                account_type=account_type,
                email_verified=True,
                **data,
            )
            if account_type in ('library', 'bookstore'):
                user.is_verified = True
                user.save(update_fields=['is_verified'])
            print(f'Created user: {user.email} ({account_type})')
        created_users.append(user)

    return created_users


def create_test_books():
    """Create some test book records without calling the Open Library API."""
    books_data = [
        {
            'isbn_13': '9780201616224',
            'isbn_10': '020161622X',
            'title': 'The Pragmatic Programmer',
            'authors': ['David Thomas', 'Andrew Hunt'],
            'publisher': 'Addison-Wesley',
            'publish_year': 1999,
            'page_count': 352,
        },
        {
            'isbn_13': '9780596007645',
            'isbn_10': '0596007647',
            'title': 'Learning Python',
            'authors': ['Mark Lutz'],
            'publisher': "O'Reilly Media",
            'publish_year': 2004,
            'page_count': 620,
        },
        {
            'isbn_13': '9780735619678',
            'isbn_10': '0735619670',
            'title': 'Code Complete',
            'authors': ['Steve McConnell'],
            'publisher': 'Microsoft Press',
            'publish_year': 2004,
            'page_count': 960,
        },
        {
            'isbn_13': '9780316769174',
            'isbn_10': '0316769177',
            'title': 'The Catcher in the Rye',
            'authors': ['J.D. Salinger'],
            'publisher': 'Little, Brown',
            'publish_year': 1951,
            'page_count': 277,
        },
        {
            'isbn_13': '9780062315007',
            'isbn_10': '0062315005',
            'title': 'Sapiens: A Brief History of Humankind',
            'authors': ['Yuval Noah Harari'],
            'publisher': 'Harper',
            'publish_year': 2015,
            'page_count': 464,
        },
    ]

    created_books = []
    for data in books_data:
        book, created = Book.objects.get_or_create(
            isbn_13=data['isbn_13'],
            defaults=data,
        )
        if created:
            print(f'Created book: {book.title}')
        else:
            print(f'Book already exists: {book.title}')
        created_books.append(book)

    return created_books


def create_test_inventory(users, books):
    """Create UserBook and WishlistItem records for test users."""
    alice, bob, carol, library = users
    prog_programmer, learning_python, code_complete, catcher, sapiens = books

    # Alice has: Pragmatic Programmer, Catcher in the Rye
    # Alice wants: Learning Python
    _add_user_book(alice, prog_programmer, 'very_good')
    _add_user_book(alice, catcher, 'good')
    _add_wishlist(alice, learning_python, 'good')

    # Bob has: Learning Python, Sapiens
    # Bob wants: Pragmatic Programmer
    _add_user_book(bob, learning_python, 'like_new')
    _add_user_book(bob, sapiens, 'very_good')
    _add_wishlist(bob, prog_programmer, 'good')

    # Carol has: Code Complete
    # Carol wants: Sapiens, Catcher in the Rye
    _add_user_book(carol, code_complete, 'acceptable')
    _add_wishlist(carol, sapiens, 'acceptable')
    _add_wishlist(carol, catcher, 'good')

    # Library wants: Learning Python, Code Complete
    _add_wishlist(library, learning_python, 'acceptable')
    _add_wishlist(library, code_complete, 'acceptable')


def _add_user_book(user, book, condition):
    ub, created = UserBook.objects.get_or_create(
        user=user, book=book, condition=condition,
        defaults={'status': 'available'},
    )
    if created:
        print(f'  {user.username} has: {book.title} ({condition})')


def _add_wishlist(user, book, min_condition):
    wi, created = WishlistItem.objects.get_or_create(
        user=user, book=book,
        defaults={'min_condition': min_condition, 'is_active': True},
    )
    if created:
        print(f'  {user.username} wants: {book.title} (min: {min_condition})')


if __name__ == '__main__':
    print('Seeding development data...\n')

    print('Creating users...')
    users = create_test_users()

    print('\nCreating books...')
    books = create_test_books()

    print('\nCreating inventory...')
    create_test_inventory(users, books)

    print('\nDone! Seed data created.')
    print('\nTest users:')
    print('  alice@example.com / testpassword123')
    print('  bob@example.com / testpassword123')
    print('  carol@example.com / testpassword123')
    print('  portlandlibrary@example.com / testpassword123 (library, verified)')
