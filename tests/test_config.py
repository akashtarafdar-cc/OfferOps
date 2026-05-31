import json
import os
import shutil
from pathlib import Path
import unittest

from offerops.config import load_app_config
from offerops.providers.cloudflare import CloudflareClient
from offerops.providers.whm import WhmClient
from offerops.state import StateStore


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        env_overrides = {
            "WHM_ECOM_LIVE_SERVER_IP": "203.0.113.20",
            "WHM_ECOM_BKP_SERVER_IP": "203.0.113.21",
            "WHM_SWEEPS_LIVE_SERVER_IP": "203.0.113.30",
            "WHM_SWEEPS_BKP_SERVER_IP": "203.0.113.31",
            "WHM_SWEEPS_LIVE_2_SERVER_IP": "203.0.113.10",
            "WHM_SWEEPS_BKP_2_SERVER_IP": "203.0.113.11",
        }
        for key, value in env_overrides.items():
            os.environ[key] = value
            self.addCleanup(os.environ.pop, key, None)

    def test_config_expands_dns_records(self) -> None:
        config = load_app_config(Path("config.json"))
        records = config.dns_records_for("ecom-live", "harborcartmarket.test")
        self.assertEqual(records[0].name, "@")
        self.assertEqual(records[0].content, "203.0.113.20")
        self.assertEqual(records[3].name, "www")
        self.assertEqual(records[3].content, "203.0.113.20")

    def test_cron_expands_domain_and_username(self) -> None:
        config = load_app_config(Path("config.json"))
        cron = config.cron_for("harborcartmarket.test", "acct", "ecom-live", "v1/msrack")
        self.assertEqual(cron.command, "php -q /home/acct/public_html/v1/msrack/library/cron.php >/dev/null 2>&1")
        self.assertIn("acct", cron.command)

    def test_cron_interval_is_stable_between_15_and_25_minutes(self) -> None:
        config = load_app_config(Path("config.json"))
        first = config.cron_for("harborcartmarket.test", "acct", "ecom-live", "v1/msrack")
        second = config.cron_for("harborcartmarket.test", "acct", "ecom-live", "v1/msrack")
        interval = int(first.minute.removeprefix("*/"))

        self.assertEqual(first.minute, second.minute)
        self.assertGreaterEqual(interval, 15)
        self.assertLessEqual(interval, 25)

    def test_sweeps_live_matches_cloudflare_export_shape(self) -> None:
        config = load_app_config(Path("config.json"))
        records = config.dns_records_for("sweeps-live", "brightbuyexchange.test")
        by_name_type = {(record.name, record.type): record for record in records}

        self.assertEqual(by_name_type[("@", "A")].content, "203.0.113.30")
        self.assertTrue(by_name_type[("@", "A")].proxied)
        self.assertFalse(by_name_type[("mail", "A")].proxied)
        self.assertFalse(by_name_type[("webmail", "A")].proxied)
        self.assertEqual(by_name_type[("@", "MX")].content, "mail.brightbuyexchange.test")
        self.assertEqual(by_name_type[("@", "MX")].priority, 10)

    def test_offer_profiles_use_real_server_ips(self) -> None:
        config = load_app_config(Path("config.json"))
        cases = {
            "ecom-live": "203.0.113.20",
            "ecom-bkp": "203.0.113.21",
            "sweeps-live": "203.0.113.30",
            "sweeps-bkp": "203.0.113.31",
        }
        for profile, ip in cases.items():
            with self.subTest(profile=profile):
                records = config.dns_records_for(profile, "harborcartmarket.test")
                by_name_type = {(record.name, record.type): record for record in records}
                self.assertEqual(by_name_type[("@", "A")].content, ip)
                self.assertEqual(by_name_type[("www", "A")].content, ip)
                self.assertEqual(by_name_type[("mail", "A")].content, ip)
                self.assertEqual(by_name_type[("webmail", "A")].content, ip)
                self.assertEqual(by_name_type[("@", "MX")].content, "mail.harborcartmarket.test")

    def test_sweeps_second_servers_use_env_backed_dns_ips(self) -> None:
        config = load_app_config(Path("config.json"))
        cases = {
            "sweeps-live-2": "203.0.113.10",
            "sweeps-bkp-2": "203.0.113.11",
        }
        for profile, ip in cases.items():
            with self.subTest(profile=profile):
                records = config.dns_records_for(profile, "harborcartmarket.test")
                by_name_type = {(record.name, record.type): record for record in records}
                self.assertEqual(by_name_type[("@", "A")].content, ip)
                self.assertEqual(by_name_type[("www", "A")].content, ip)

    def test_profiles_route_to_expected_cloudflare_accounts(self) -> None:
        config = load_app_config(Path("config.json"))
        self.assertEqual(config.cloudflare_account_for("ecom-live"), "ecom")
        self.assertEqual(config.cloudflare_account_for("ecom-bkp"), "ecom")
        self.assertEqual(config.cloudflare_account_for("sweeps-live"), "sweeps")
        self.assertEqual(config.cloudflare_account_for("sweeps-bkp"), "sweeps")
        self.assertEqual(config.cloudflare_account_for("sweeps-live-2"), "sweeps")
        self.assertEqual(config.cloudflare_account_for("sweeps-bkp-2"), "sweeps")

    def test_profiles_route_to_expected_whm_accounts(self) -> None:
        config = load_app_config(Path("config.json"))
        self.assertEqual(config.whm_account_for("ecom-live"), "ecom_live")
        self.assertEqual(config.whm_account_for("ecom-bkp"), "ecom_bkp")
        self.assertEqual(config.whm_account_for("sweeps-live"), "sweeps_live")
        self.assertEqual(config.whm_account_for("sweeps-bkp"), "sweeps_bkp")
        self.assertEqual(config.whm_account_for("sweeps-live-2"), "sweeps_live_2")
        self.assertEqual(config.whm_account_for("sweeps-bkp-2"), "sweeps_bkp_2")

    def test_profile_lookup_accepts_spaced_server_names(self) -> None:
        config = load_app_config(Path("config.json"))
        self.assertEqual(config.whm_account_for("sweeps live 2"), "sweeps_live_2")
        self.assertEqual(config.whm_account_for("sweeps bkp 2"), "sweeps_bkp_2")

    def test_server_choices_are_grouped_by_kind(self) -> None:
        config = load_app_config(Path("config.json"))
        self.assertEqual(config.server_choices_for_kind("ecom"), ["live", "bkp"])
        self.assertEqual(config.server_choices_for_kind("sweeps"), ["live", "live-2", "bkp", "bkp-2"])

    def test_kind_and_server_resolve_to_profile(self) -> None:
        config = load_app_config(Path("config.json"))
        self.assertEqual(config.resolve_profile_for_kind_server("ecom", "live"), "ecom-live")
        self.assertEqual(config.resolve_profile_for_kind_server("sweeps", "live-2"), "sweeps-live-2")
        self.assertEqual(config.resolve_profile_for_kind_server("sweeps", "bkp 2"), "sweeps-bkp-2")

    def test_orange_accounts_are_scoped_by_profile_group(self) -> None:
        config = load_app_config(Path("config.json"))
        self.assertEqual(
            config.orange_account_names_for("sweeps-live"),
            ["sweeps_live", "sweeps_bkp", "sweeps_live_2", "sweeps_bkp_2"],
        )
        self.assertEqual(
            config.orange_account_names_for("ecom-live"),
            ["ecom_live", "ecom_bkp"],
        )

    def test_cloudflare_bot_fight_mode_defaults_to_enabled(self) -> None:
        config = load_app_config(Path("config.json"))
        self.assertTrue(config.cloudflare_bot_fight_mode_enabled())

    def test_default_robots_blocks_root_and_google_images(self) -> None:
        config = load_app_config(Path("config.json"))
        robots = config.defaults["robots_txt"]
        self.assertIn("Disallow: /", robots)
        self.assertIn("User-agent: Googlebot-Image", robots)
        self.assertIn("Disallow: /*.png$", robots)

    def test_document_root_defaults_to_public_html(self) -> None:
        config = load_app_config(Path("config.json"))
        self.assertEqual(config.document_root_for("harborcartmarket.test"), "public_html")

    def test_whm_username_follows_domain_short_form(self) -> None:
        self.assertEqual(WhmClient.username_for_domain("ModernPicksShoppingMarket.com"), "modernpicksshopp")
        self.assertEqual(WhmClient.username_for_domain("clevercartcorner.com"), "clevercartcorner")

    def test_whm_cpanel_login_url_uses_2083(self) -> None:
        self.assertEqual(
            WhmClient.cpanel_login_url("https://node.reliabletradeexchange.com:2087"),
            "https://node.reliabletradeexchange.com:2083",
        )

    def test_database_user_keeps_full_username_prefix(self) -> None:
        client = WhmClient("https://cpanel.harborcartmarket.test:2087", "root", "token", dry_run=True)
        created = client.create_database_user("clevercartcorner", "clevercartcorner.test", "pass")
        self.assertEqual(created["database"], "clevercartcorner_db")
        self.assertEqual(created["user"], "clevercartcorner_user")

    def test_email_deliverability_helpers_parse_uapi_shape(self) -> None:
        client = WhmClient("https://cpanel.harborcartmarket.test:2087", "root", "token", dry_run=False)

        def fake_uapi(cpanel_username: str, module: str, function: str, **params: object) -> dict[str, object]:
            if function == "validate_current_dkims":
                return {
                    "status": 1,
                    "data": [
                        {
                            "domain": "default._domainkey.harborcartmarket.test",
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
                            "domain": "harborcartmarket.test",
                            "expected": "ip4:203.0.113.30",
                            "record": None,
                        }
                    ],
                }
            if function == "validate_current_dmarcs":
                return {
                    "status": 1,
                    "data": [
                        {
                            "subdomain": "_dmarc.harborcartmarket.test",
                            "suggested": "v=DMARC1; p=none;",
                            "record": None,
                        }
                    ],
                }
            raise AssertionError(function)

        client.uapi = fake_uapi  # type: ignore[method-assign]
        records = client.email_deliverability_records("example", "harborcartmarket.test")
        self.assertEqual(
            records,
            [
                {"type": "TXT", "name": "default._domainkey.harborcartmarket.test", "content": "v=DKIM1; k=rsa; p=test"},
                {"type": "TXT", "name": "harborcartmarket.test", "content": "v=spf1 +a +mx +ip4:203.0.113.30 ~all"},
                {"type": "TXT", "name": "_dmarc.harborcartmarket.test", "content": "v=DMARC1; p=none;"},
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

    def test_cloudflare_bot_fight_mode_payload(self) -> None:
        client = CloudflareClient("token", "acct", dry_run=False)

        class FakeResponse:
            def __init__(self, body: dict[str, object]) -> None:
                self.body = body

        captured: dict[str, object] = {}

        def fake_request(method: str, path: str, **kwargs: object) -> FakeResponse:
            captured["method"] = method
            captured["path"] = path
            captured["json_body"] = kwargs.get("json_body")
            return FakeResponse({"result": {"id": "bot_fight_mode", "value": "on"}})

        client.http.request = fake_request  # type: ignore[method-assign]

        result = client.set_bot_fight_mode("zone-123", True)

        self.assertEqual(captured["method"], "PATCH")
        self.assertEqual(captured["path"], "/zones/zone-123/settings/bot_fight_mode")
        self.assertEqual(captured["json_body"], {"value": "on"})
        self.assertEqual(result["value"], "on")

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
            output = store.save_credentials("harborcartmarket.test", {"cpanel_username": "example"})
            self.assertTrue(output.exists())
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["cpanel_username"], "example")
        finally:
            if tempdir.exists():
                shutil.rmtree(tempdir)


if __name__ == "__main__":
    unittest.main()
