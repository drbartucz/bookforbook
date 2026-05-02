import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from apps.books.services.barcode import (
    _normalize_raw,
    _validate_isbn10,
    _validate_isbn13,
    extract_isbn_from_image,
)


def test_validate_isbn13():
    assert _validate_isbn13("9780141036144") is True
    assert _validate_isbn13("9780141036145") is False
    assert _validate_isbn13("123") is False
    assert _validate_isbn13("notdigits1234") is False


def test_validate_isbn10():
    # Valid ISBN-10s
    assert _validate_isbn10("0316015849") is True
    assert _validate_isbn10("8090273416") is True
    assert _validate_isbn10("0141036148") is False 
    assert _validate_isbn10("014103614X") is False  # Incorrect check digit
    assert _validate_isbn10("123") is False
    assert _validate_isbn10("X123456789") is False


def test_normalize_raw():
    # Valid ISBN-13
    assert _normalize_raw("978-0-141-03614-4") == "9780141036144"
    assert _normalize_raw(" 9780141036144 ") == "9780141036144"
    # Valid ISBN-10 to ISBN-13
    assert _normalize_raw("0316015849") == "9780316015844"
    # Invalid
    assert _normalize_raw("12345") is None


@patch("apps.books.services.barcode.Image.open")
def test_extract_isbn_from_image_no_pyzbar(mock_open):
    # Create a dummy image for the open mock
    img = Image.new("RGB", (10, 10))
    mock_open.return_value = img
    
    # We need to mock the import failure of pyzbar
    with patch("builtins.__import__") as mock_import:
        def side_effect(name, *args, **kwargs):
            if name == "pyzbar":
                raise ImportError("test")
            return MagicMock()
        mock_import.side_effect = side_effect
        
        with pytest.raises(ImportError, match="pyzbar is not installed"):
            extract_isbn_from_image(io.BytesIO())


@patch("apps.books.services.barcode._preprocess_variants")
def test_extract_isbn_from_image_success(mock_preprocess):
    # Create a dummy image
    img = Image.new("RGB", (10, 10), color="white")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)

    # Mock variants to avoid PIL filter issues during mock
    mock_preprocess.return_value = [img]

    # Mock pyzbar.decode by mocking the import inside extract_isbn_from_image
    with patch("builtins.__import__") as mock_import:
        mock_pyzbar = MagicMock()
        mock_import.return_value = mock_pyzbar
        
        mock_obj = MagicMock()
        mock_obj.data = b"9780141036144"
        mock_pyzbar.pyzbar.decode.return_value = [mock_obj]

        isbn = extract_isbn_from_image(img_byte_arr)
        assert isbn == "9780141036144"


@patch("apps.books.services.barcode._preprocess_variants")
def test_extract_isbn_from_image_failure(mock_preprocess):
    # Create a dummy image
    img = Image.new("RGB", (10, 10), color="white")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)
    
    mock_preprocess.return_value = [img]

    with patch("builtins.__import__") as mock_import:
        mock_pyzbar = MagicMock()
        mock_import.return_value = mock_pyzbar
        mock_pyzbar.pyzbar.decode.return_value = []

        isbn = extract_isbn_from_image(img_byte_arr)
        assert isbn is None


@patch("apps.books.services.barcode.Image.open")
def test_extract_isbn_from_image_invalid_image(mock_open):
    mock_open.side_effect = Exception("Invalid image")
    
    # We need to mock pyzbar import so it doesn't fail on system lib missing
    with patch("builtins.__import__") as mock_import:
        mock_import.return_value = MagicMock()
        with pytest.raises(ValueError, match="Cannot parse image"):
            extract_isbn_from_image(io.BytesIO(b"not an image"))
