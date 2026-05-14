import io
import json
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
import unittest

from offerops import cli
from offerops.config import load_app_config, load_settings
from offerops.runner import OfferProvisioner


class CliTests(unittest.TestCase):
    def test_orange_ns_command_runs_only_orange_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "config.json"
            state_path = root / "jobs.json"
            config_path.write_text(
                json.dumps(
                    {
                        "defaults": {},
                        "profiles": {
                            "sweeps-live": {
                                "cloudflare_account": "sweeps",
                                "whm_account": "sweeps_live",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            with patch.dict(
                "os.environ",
                {
                    "OFFEROPS_CONFIG": str(config_path),
                    "OFFEROPS_STATE": str(state_path),
                },
                clear=False,
            ):
                with patch("offerops.runner.CloudflareClient.ensure_zone", return_value={"id": "zone", "name_servers": ["ns1.example.com", "ns2.example.com"]}):
                    with patch("offerops.runner.OrangeBrowserClient.update_nameservers", return_value={"ok": True}) as update_mock:
                        buffer = io.StringIO()
                        with redirect_stdout(buffer):
                            with patch("sys.argv", ["offerops", "orange-ns", "--domain", "example.com", "--profile", "sweeps-live", "--dry-run"]):
                                cli.main()

        update_mock.assert_called_once_with("example.com", ["ns1.example.com", "ns2.example.com"])
        self.assertIn('"ok": true', buffer.getvalue().lower())

    def test_orange_ns_uses_only_matching_orange_accounts_for_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "config.json"
            state_path = root / "jobs.json"
            config_path.write_text(
                json.dumps(
                    {
                        "defaults": {},
                        "profiles": {
                            "ecom-live": {
                                "cloudflare_account": "ecom",
                                "whm_account": "ecom_live",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            env = {
                "OFFEROPS_CONFIG": str(config_path),
                "OFFEROPS_STATE": str(state_path),
                "ORANGE_ECOM_LIVE_USERNAME": "ecom-user",
                "ORANGE_ECOM_LIVE_PASSWORD": "ecom-pass",
                "ORANGE_ECOM_BKP_USERNAME": "ecom-bkp-user",
                "ORANGE_ECOM_BKP_PASSWORD": "ecom-bkp-pass",
                "ORANGE_SWEEPS_LIVE_USERNAME": "sweeps-user",
                "ORANGE_SWEEPS_LIVE_PASSWORD": "sweeps-pass",
            }
            with patch.dict("os.environ", env, clear=False):
                settings = load_settings()
                config = load_app_config(config_path)
                provisioner = OfferProvisioner(settings, config, state=None, dry_run=True, use_orange_browser=True)  # type: ignore[arg-type]

                with patch("offerops.runner.CloudflareClient.ensure_zone", return_value={"id": "zone", "name_servers": ["ns1.ecom.example.com", "ns2.ecom.example.com"]}):
                    result = provisioner.run_orange_nameserver_update("example.com", "ecom-live")

        self.assertEqual(result["searched_accounts"], ["ecom_live", "ecom_bkp"])


if __name__ == "__main__":
    unittest.main()
