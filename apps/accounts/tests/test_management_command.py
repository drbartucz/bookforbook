import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


pytestmark = pytest.mark.django_db


def test_smoke_test_usps_token_only_outputs_success(capsys):
    from unittest.mock import patch

    with patch(
        "apps.accounts.management.commands.smoke_test_usps._get_oauth_token",
        return_value="mock-token-value",
    ):
        call_command("smoke_test_usps", "--token-only")

    captured = capsys.readouterr()
    assert "OAuth token acquired" in captured.out
    assert "Token-only smoke test passed." in captured.out


def test_smoke_test_usps_requires_address_args_without_token_only():
    from unittest.mock import patch

    with patch(
        "apps.accounts.management.commands.smoke_test_usps._get_oauth_token",
        return_value="mock-token-value",
    ):
        with pytest.raises(CommandError) as exc:
            call_command("smoke_test_usps")

    assert "Address lookup requires these arguments" in str(exc.value)


def test_smoke_test_usps_address_lookup_outputs_normalized_address(capsys):
    from unittest.mock import patch

    with patch(
        "apps.accounts.management.commands.smoke_test_usps._get_oauth_token",
        return_value="mock-token-value",
    ), patch(
        "apps.accounts.management.commands.smoke_test_usps.verify_address_with_usps",
        return_value={
            "address_line_1": "123 MAIN ST",
            "address_line_2": "APT 2",
            "city": "DENVER",
            "state": "CO",
            "zip_code": "80202-1234",
        },
    ):
        call_command(
            "smoke_test_usps",
            "--street-address=123 Main Street",
            "--secondary-address=Apt 2",
            "--city=Denver",
            "--state=CO",
            "--zip-code=80202",
        )

    captured = capsys.readouterr()
    assert "Address verification passed." in captured.out
    assert "123 MAIN ST" in captured.out
    assert "80202-1234" in captured.out
