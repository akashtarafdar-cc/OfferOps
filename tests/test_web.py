import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from offerops.config import AppConfig, Settings
from offerops.models import JobResult, StepStatus
from offerops.state import StateStore
from offerops.web import RunManager


class RunManagerTests(unittest.TestCase):
    def test_start_run_accepts_multiple_domain_slug_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager(Path(tmp))
            with patch("offerops.web.threading.Thread.start", return_value=None):
                result = manager.start_run(
                    {
                        "kind": "sweeps",
                        "server": "live",
                        "job_rows": [
                            {"domain": "alpha.test", "offer_path": "v1/msrack"},
                            {"domain": "beta.test", "offer_path": "https://beta.test/v2/offer"},
                        ],
                        "dry_run": True,
                        "orange_browser": False,
                    }
                )

            run = manager.get_run(result["run_id"])

        self.assertIsNotNone(run)
        self.assertEqual(run["profile"], "sweeps-live")
        self.assertEqual(
            [(job["domain"], job["offer_path"]) for job in run["jobs"]],
            [("alpha.test", "v1/msrack"), ("beta.test", "v2/offer")],
        )

    def test_start_run_falls_back_to_shared_slug_and_domain_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager(Path(tmp))
            with patch("offerops.web.threading.Thread.start", return_value=None):
                result = manager.start_run(
                    {
                        "kind": "sweeps",
                        "server": "live",
                        "offer_path": "v1/msrack",
                        "domains": "alpha.test\nbeta.test",
                        "dry_run": True,
                        "orange_browser": False,
                    }
                )

            run = manager.get_run(result["run_id"])

        self.assertIsNotNone(run)
        self.assertEqual(
            [(job["domain"], job["offer_path"]) for job in run["jobs"]],
            [("alpha.test", "v1/msrack"), ("beta.test", "v1/msrack")],
        )

    def test_start_run_rejects_incomplete_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = self._manager(Path(tmp))
            with patch("offerops.web.threading.Thread.start", return_value=None):
                with self.assertRaisesRegex(ValueError, "Slug / offer path is required for alpha.test"):
                    manager.start_run(
                        {
                            "kind": "sweeps",
                            "server": "live",
                            "job_rows": [{"domain": "alpha.test", "offer_path": ""}],
                            "dry_run": True,
                            "orange_browser": False,
                        }
                    )

    def test_clear_history_removes_saved_runs_and_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = StateStore(root / "state.json")
            state.save_result(JobResult(domain="alpha.test", profile="sweeps-live", status=StepStatus.DONE))
            state.save_credentials("alpha.test", {"domain": "alpha.test", "profile": "sweeps-live"})

            state.clear_history()

        self.assertFalse((root / "state.json").exists())
        self.assertFalse((root / "credentials").exists())

    def test_get_credentials_reads_saved_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = StateStore(Path(tmp) / "state.json")
            state.save_credentials(
                "alpha.test",
                {
                    "domain": "alpha.test",
                    "profile_kind": "sweeps-live",
                    "support_email": "support@alpha.test",
                },
            )

            payload = state.get_credentials("alpha.test")

        self.assertIsNotNone(payload)
        self.assertEqual(payload["domain"], "alpha.test")
        self.assertEqual(payload["support_email"], "support@alpha.test")

    def _manager(self, root: Path) -> RunManager:
        settings = Settings(
            config_path=root / "config.json",
            state_path=root / "state.json",
            cloudflare_accounts={},
            whm_accounts={},
            orange_login_url="",
            orange_headless=True,
            orange_accounts={},
        )
        config = AppConfig(
            {
                "defaults": {},
                "profiles": {
                    "sweeps-live": {
                        "kind": "sweeps",
                        "servers": ["live"],
                        "cloudflare_account": "sweeps",
                        "whm_account": "sweeps_live",
                    }
                },
            }
        )
        state = StateStore(settings.state_path)
        return RunManager(settings, config, state)


if __name__ == "__main__":
    unittest.main()
