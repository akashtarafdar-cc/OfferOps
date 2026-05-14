import unittest
import os
from pathlib import Path

from offerops.config import Settings, load_app_config
from offerops.http import HttpError, HttpResponse
from offerops.models import DomainJob, StepStatus
from offerops.runner import OfferProvisioner
from offerops.state import StateStore


class RunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["WHM_SWEEPS_LIVE_2_SERVER_IP"] = "203.0.113.10"
        self.addCleanup(os.environ.pop, "WHM_SWEEPS_LIVE_2_SERVER_IP", None)

    def test_bot_fight_mode_403_is_skipped_and_run_continues(self) -> None:
        settings = Settings(
            config_path=Path("config.json"),
            state_path=Path(".tmp/test-runner/jobs.json"),
            cloudflare_accounts={"sweeps": ("token", "acct")},
            whm_accounts={"sweeps_live_2": ("https://example.test:2087", "root", "token", "package", "ops@example.test")},
            orange_login_url="https://secure.orangewebsite.com/login",
            orange_headless=False,
            orange_accounts={"sweeps_live_2": ("user", "pass")},
        )
        config = load_app_config(Path("config.json"))
        state = StateStore(settings.state_path)
        provisioner = OfferProvisioner(settings, config, state, dry_run=True, use_orange_browser=False)

        cloudflare = provisioner._cloudflare_for("sweeps-live-2")

        def fail_bot_fight(zone_id: str, enabled: bool = True) -> dict[str, object]:
            raise HttpError(
                "PATCH https://api.cloudflare.com/client/v4/zones/zone/settings/bot_fight_mode failed with HTTP 403",
                HttpResponse(status=403, body={}, headers={}),
            )

        cloudflare.set_bot_fight_mode = fail_bot_fight  # type: ignore[method-assign]
        provisioner._cloudflare_for = lambda profile_name: cloudflare  # type: ignore[method-assign]

        result = provisioner.run(DomainJob(domain="urbanprairiefinds.com", profile="sweeps-live-2", offer_path="v1/msrack"))

        steps = {step.name: step for step in result.steps}
        self.assertEqual(steps["cloudflare-zone"].status, StepStatus.DONE)
        self.assertEqual(steps["cloudflare-bot-fight-mode"].status, StepStatus.SKIPPED)
        self.assertEqual(steps["orange-nameservers"].status, StepStatus.DONE)
        self.assertEqual(
            steps["orange-nameservers"].data["nameservers"],
            ["dry.ns.cloudflare.com", "dry2.ns.cloudflare.com"],
        )
        self.assertEqual(
            steps["secrets"].data["nameservers"],
            ["dry.ns.cloudflare.com", "dry2.ns.cloudflare.com"],
        )
        self.assertEqual(result.status, StepStatus.DONE)

    def test_preferred_nameservers_requires_live_zone_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "did not return zone nameservers"):
            OfferProvisioner._preferred_nameservers({"id": "zone"})


if __name__ == "__main__":
    unittest.main()
