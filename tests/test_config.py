import json
import shutil
from pathlib import Path
import unittest

from offerops.config import load_app_config
from offerops.providers.cloudflare import CloudflareClient
from offerops.providers.whm import WhmClient
from offerops.state import StateStore


class ConfigTests(unittest.TestCase):
    def test_config_expands_dns_records(self) -> None:
        config = load_app_config(Path("config.example.json"))
        records = config.dns_records_for("ecom-live", "example.com")
        self.assertEqual(records[0].name, "@")
        self.assertEqual(records[0].content, "82.221.128.163")
        self.assertEqual(records[3].name, "www")
        self.assertEqual(records[3].content, "82.221.128.163")

    def test_cron_expands_domain_and_username(self) -> None:
        config = load_app_config(Path("config.example.json"))
        cron = config.cron_for("example.com", "acct", "ecom-live", "v1/msrack")
        self.assertEqual(cron.command, "php -q /home/acct/public_html/v1/msrack/library/cron.php >/dev/null 2>&1")
        self.assertIn("acct", cron.command)

    def test_cron_interval_is_stable_between_15_and_25_minutes(self) -> None:
        config = load_app_config(Path("config.example.json"))
        first = config.cron_for("example.com", "acct", "ecom-live", "v1/msrack")
        second = config.cron_for("example.com", "acct", "ecom-live", "v1/msrack")
        interval = int(first.minute.removeprefix("*/"))

        self.assertEqual(first.minute, second.minute)
        self.assertGreaterEqual(interval, 15)
        self.assertLessEqual(interval, 25)

    def test_sweeps_live_matches_cloudflare_export_shape(self) -> None:
        config = load_app_config(Path("config.example.json"))
        records = config.dns_records_for("sweeps-live", "brightbuyexchange.com")
        by_name_type = {(record.name, record.type): record for record in records}

        self.assertEqual(by_name_type[("@", "A")].content, "82.221.131.39")
        self.assertTrue(by_name_type[("@", "A")].proxied)
        self.assertFalse(by_name_type[("mail", "A")].proxied)
        self.assertFalse(by_name_type[("webmail", "A")].proxied)
        self.assertEqual(by_name_type[("@", "MX")].content, "mail.brightbuyexchange.com")
        self.assertEqual(by_name_type[("@", "MX")].priority, 10)

    def test_offer_profiles_use_real_server_ips(self) -> None:
        config = load_app_config(Path("config.example.json"))
        cases = {
            "ecom-live": "82.221.128.163",
            "ecom-bkp": "82.221.143.71",
            "sweeps-live": "82.221.131.39",
            "sweeps-bkp": "82.221.131.16",
        }
        for profile, ip in cases.items():
            with self.subTest(profile=profile):
                records = config.dns_records_for(profile, "example.com")
                by_name_type = {(record.name, record.type): record for record in records}
                self.assertEqual(by_name_type[("@", "A")].content, ip)
                self.assertEqual(by_name_type[("www", "A")].content, ip)
                self.assertEqual(by_name_type[("mail", "A")].content, ip)
                self.assertEqual(by_name_type[("webmail", "A")].content, ip)
                self.assertEqual(by_name_type[("@", "MX")].content, "mail.example.com")

    def test_profiles_route_to_expected_cloudflare_accounts(self) -> None:
        config = load_app_config(Path("config.example.json"))
        self.assertEqual(config.cloudflare_account_for("ecom-live"), "ecom")
        self.assertEqual(config.cloudflare_account_for("ecom-bkp"), "ecom")
        self.assertEqual(config.cloudflare_account_for("sweeps-live"), "sweeps")
        self.assertEqual(config.cloudflare_account_for("sweeps-bkp"), "sweeps")

    def test_profiles_route_to_expected_whm_accounts(self) -> None:
        config = load_app_config(Path("config.example.json"))
        self.assertEqual(config.whm_account_for("ecom-live"), "ecom_live")
        self.assertEqual(config.whm_account_for("ecom-bkp"), "ecom_bkp")
        self.assertEqual(config.whm_account_for("sweeps-live"), "sweeps_live")
        self.assertEqual(config.whm_account_for("sweeps-bkp"), "sweeps_bkp")

    def test_cloudflare_nameservers_are_configured_by_account(self) -> None:
        config = load_app_config(Path("config.example.json"))
        self.assertEqual(
            config.cloudflare_nameservers_for("sweeps-live"),
            ["addilyn.ns.cloudflare.com", "armfazh.ns.cloudflare.com"],
        )
        self.assertEqual(
            config.cloudflare_nameservers_for("ecom-live"),
            ["gwen.ns.cloudflare.com", "merlin.ns.cloudflare.com"],
        )

    def test_default_robots_blocks_root_and_google_images(self) -> None:
        config = load_app_config(Path("config.example.json"))
        robots = config.defaults["robots_txt"]
        self.assertIn("Disallow: /", robots)
        self.assertIn("User-agent: Googlebot-Image", robots)
        self.assertIn("Disallow: /*.png$", robots)

    def test_document_root_defaults_to_public_html(self) -> None:
        config = load_app_config(Path("config.example.json"))
        self.assertEqual(config.document_root_for("example.com"), "public_html")

    def test_whm_username_follows_domain_short_form(self) -> None:
        self.assertEqual(WhmClient.username_for_domain("ModernPicksShoppingMarket.com"), "modernpicksshopp")
        self.assertEqual(WhmClient.username_for_domain("clevercartcorner.com"), "clevercartcorner")

    def test_whm_cpanel_login_url_uses_2083(self) -> None:
        self.assertEqual(
            WhmClient.cpanel_login_url("https://node.reliabletradeexchange.com:2087"),
            "https://node.reliabletradeexchange.com:2083",
        )

    def test_database_user_keeps_full_username_prefix(self) -> None:
        client = WhmClient("https://example.com:2087", "root", "token", dry_run=True)
        created = client.create_database_user("clevercartcorner", "clevercartcorner.com", "pass")
        self.assertEqual(created["database"], "clevercartcorner_db")
        self.assertEqual(created["user"], "clevercartcorner_user")

    def test_email_deliverability_helpers_parse_uapi_shape(self) -> None:
        client = WhmClient("https://example.com:2087", "root", "token", dry_run=False)

        def fake_uapi(cpanel_username: str, module: str, function: str, **params: object) -> dict[str, object]:
            if function == "validate_current_dkims":
                return {
                    "status": 1,
                    "data": [
                        {
                            "domain": "default._domainkey.example.com",
                            "expected": "v=DKIM1; k=rsa; p=test",
                            "record": None,
                        }
                    ],
                }
            if function == "validate_current_spfs":
                return {
                    "status": 1,
                    "data": [
                        {
                            "domain": "example.com",
                            "expected": "ip4:82.221.131.39",
                            "record": None,
                        }
                    ],
                }
            if function == "validate_current_dmarcs":
                return {
                    "status": 1,
                    "data": [
                        {
                            "subdomain": "_dmarc.example.com",
                            "suggested": "v=DMARC1; p=none;",
                            "record": None,
                        }
                    ],
                }
            raise AssertionError(function)

        client.uapi = fake_uapi  # type: ignore[method-assign]
        records = client.email_deliverability_records("example", "example.com")
        self.assertEqual(
            records,
            [
                {"type": "TXT", "name": "default._domainkey.example.com", "content": "v=DKIM1; k=rsa; p=test"},
                {"type": "TXT", "name": "example.com", "content": "v=spf1 +a +mx +ip4:82.221.131.39 ~all"},
                {"type": "TXT", "name": "_dmarc.example.com", "content": "v=DMARC1; p=none;"},
            ],
        )

    def test_generated_password_is_sheet_friendly(self) -> None:
        password = WhmClient.random_password()
        self.assertEqual(len(password), 16)
        self.assertNotIn("=", password)

    def test_cloudflare_normalizes_apex_name(self) -> None:
        self.assertEqual(CloudflareClient._normalize_name("@", "clevercartcorner.com"), "clevercartcorner.com")
        self.assertEqual(CloudflareClient._normalize_name("www", "clevercartcorner.com"), "www.clevercartcorner.com")
        self.assertEqual(CloudflareClient._normalize_name("_dmarc", "clevercartcorner.com"), "_dmarc.clevercartcorner.com")
        self.assertEqual(
            CloudflareClient._normalize_name("default._domainkey.clevercartcorner.com", "clevercartcorner.com"),
            "default._domainkey.clevercartcorner.com",
        )

    def test_package_error_detection(self) -> None:
        self.assertTrue(
            WhmClient._is_package_error(
                "Sorry, unable to use package default. Verify that the package exists and that you have not exceeded your reseller restrictions."
            )
        )
        self.assertFalse(WhmClient._is_package_error("A completely different WHM error"))

    def test_credentials_are_saved_in_separate_file(self) -> None:
        tempdir = Path(".tmp/test-state-store")
        if tempdir.exists():
            shutil.rmtree(tempdir)
        tempdir.mkdir(parents=True)
        try:
            store = StateStore(tempdir / "jobs.json")
            output = store.save_credentials("example.com", {"cpanel_username": "example"})
            self.assertTrue(output.exists())
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["cpanel_username"], "example")
        finally:
            if tempdir.exists():
                shutil.rmtree(tempdir)


if __name__ == "__main__":
    unittest.main()
