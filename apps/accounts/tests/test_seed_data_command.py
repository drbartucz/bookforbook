import pytest
from django.core.management import call_command

from apps.accounts.models import User
from apps.books.models import Book
from apps.inventory.models import UserBook, WishlistItem


pytestmark = pytest.mark.django_db


def test_seed_data_small_creates_expected_base_dataset():
    call_command("seed_data", "--size=small", "--seed=42", "--password=testpass123")

    assert (
        User.objects.filter(
            email__in=[
                "alice@example.com",
                "bob@example.com",
                "carol@example.com",
                "portlandlibrary@example.com",
            ]
        ).count()
        == 4
    )
    assert (
        Book.objects.filter(
            isbn_13__in=[
                "9780201616224",
                "9780596007645",
                "9780735619678",
                "9780316769174",
                "9780062315007",
            ]
        ).count()
        == 5
    )
    assert UserBook.objects.count() == 5
    assert WishlistItem.objects.count() == 6

    pragmatic = Book.objects.get(isbn_13="9780201616224")
    assert pragmatic.cover_image_url
    assert "covers.openlibrary.org" in pragmatic.cover_image_url


def test_seed_data_small_is_idempotent_without_reset():
    call_command("seed_data", "--size=small", "--seed=42")
    call_command("seed_data", "--size=small", "--seed=99")

    assert User.objects.count() == 4
    assert Book.objects.count() == 5
    assert UserBook.objects.count() == 5
    assert WishlistItem.objects.count() == 6


def test_seed_data_medium_creates_generated_users_and_books():
    call_command("seed_data", "--size=medium", "--seed=42")

    assert User.objects.count() == 12  # 4 base + 8 generated
    assert User.objects.filter(email__startswith="seed_user_").count() == 8

    assert Book.objects.count() == 25  # 5 base + 20 generated
    assert Book.objects.filter(isbn_13__startswith="978111111").count() == 20

    assert UserBook.objects.count() == 45  # 5 core + (8 generated * 5 each)
    assert WishlistItem.objects.count() == 46  # 6 core + (8 generated * 5 each)
