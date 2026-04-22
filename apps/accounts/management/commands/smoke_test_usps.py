from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.services.usps import (
    USPSVerificationError,
    _get_oauth_token,
    verify_address_with_usps,
)


class Command(BaseCommand):
    help = "Smoke-test USPS OAuth and address verification integration"

    def add_arguments(self, parser):
        parser.add_argument(
            "--token-only",
            action="store_true",
            help="Only test OAuth token retrieval and stop before address lookup.",
        )
        parser.add_argument("--street-address", help="Street address line 1")
        parser.add_argument(
            "--secondary-address",
            default="",
            help="Secondary address information such as apartment or suite",
        )
        parser.add_argument("--city", help="City name")
        parser.add_argument("--state", help="Two-letter state code")
        parser.add_argument("--zip-code", help="ZIP code or ZIP+4")

    def handle(self, *args, **options):
        self.stdout.write("USPS smoke test")
        self.stdout.write(f"  OAuth base URL: {settings.USPS_OAUTH_BASE_URL}")
        self.stdout.write(f"  Addresses base URL: {settings.USPS_ADDRESSES_BASE_URL}")

        try:
            token = _get_oauth_token()
        except USPSVerificationError as exc:
            raise CommandError(f"OAuth token request failed: {exc}") from exc

        token_preview = f"{token[:12]}..." if len(token) > 12 else token
        self.stdout.write(self.style.SUCCESS(f"OAuth token acquired: {token_preview}"))

        if options["token_only"]:
            self.stdout.write(self.style.SUCCESS("Token-only smoke test passed."))
            return

        required_args = ["street_address", "city", "state", "zip_code"]
        missing = [name for name in required_args if not options.get(name)]
        if missing:
            formatted = ", ".join(f"--{name.replace('_', '-')}" for name in missing)
            raise CommandError(
                f"Address lookup requires these arguments unless --token-only is used: {formatted}"
            )

        try:
            normalized = verify_address_with_usps(
                address_line_1=options["street_address"],
                address_line_2=options["secondary_address"],
                city=options["city"],
                state=options["state"],
                zip_code=options["zip_code"],
            )
        except USPSVerificationError as exc:
            raise CommandError(f"Address verification failed: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("Address verification passed."))
        self.stdout.write("Normalized address:")
        self.stdout.write(f"  full street: {normalized['address_line_1']}")
        if normalized["address_line_2"]:
            self.stdout.write(f"  secondary: {normalized['address_line_2']}")
        self.stdout.write(f"  city: {normalized['city']}")
        self.stdout.write(f"  state: {normalized['state']}")
        self.stdout.write(f"  zip: {normalized['zip_code']}")
