from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import CronSpec, DnsRecord


@dataclass(frozen=True)
class Settings:
    config_path: Path
    state_path: Path
    cloudflare_accounts: dict[str, tuple[str, str]]
    whm_accounts: dict[str, tuple[str, str, str, str, str]]
    orange_login_url: str
    orange_headless: bool
    orange_accounts: dict[str, tuple[str, str]]


@dataclass(frozen=True)
class AppConfig:
    raw: dict[str, Any]

    @property
    def defaults(self) -> dict[str, Any]:
        return dict(self.raw.get("defaults", {}))

    def profile(self, name: str) -> dict[str, Any]:
        profiles = self.raw.get("profiles", {})
        if name not in profiles:
            raise KeyError(f"Unknown profile '{name}'. Add it under profiles in config.")
        return dict(profiles[name])

    def cloudflare_account_for(self, profile_name: str) -> str:
        return str(self.profile(profile_name)["cloudflare_account"])

    def whm_account_for(self, profile_name: str) -> str:
        return str(self.profile(profile_name)["whm_account"])

    def cloudflare_nameservers_for(self, profile_name: str) -> list[str]:
        account_name = self.cloudflare_account_for(profile_name)
        configured = self.defaults.get("cloudflare_nameservers", {})
        if isinstance(configured, dict):
            return [str(item) for item in configured.get(account_name, [])]
        return [str(item) for item in configured]

    def dns_records_for(self, profile_name: str, domain: str) -> list[DnsRecord]:
        profile = self.profile(profile_name)
        ttl = int(self.defaults.get("dns_ttl", 1))
        return [DnsRecord.from_dict(item, domain, ttl) for item in profile.get("dns_records", [])]

    def cron_for(self, domain: str, cpanel_username: str, profile_name: str, offer_path: str) -> CronSpec:
        cron = dict(self.defaults.get("cron", {}))
        cron.update(self.profile(profile_name).get("cron", {}))
        minute = str(cron.get("minute", ""))
        if not minute:
            minute_min = int(cron.get("minute_min", 15))
            minute_max = int(cron.get("minute_max", 25))
            minute = f"*/{self._stable_random_interval(domain, profile_name, minute_min, minute_max)}"
        return CronSpec(
            minute=minute,
            hour=str(cron.get("hour", "*")),
            day=str(cron.get("day", "*")),
            month=str(cron.get("month", "*")),
            weekday=str(cron.get("weekday", "*")),
            command=str(cron["command_template"]).format(domain=domain, cpanel_username=cpanel_username, offer_path=offer_path),
        )

    def document_root_for(self, domain: str) -> str:
        template = str(self.defaults.get("document_root_template", "public_html"))
        return template.format(domain=domain)

    @staticmethod
    def _stable_random_interval(domain: str, profile_name: str, minute_min: int, minute_max: int) -> int:
        if minute_min > minute_max:
            raise ValueError("cron minute_min cannot be greater than minute_max")
        rng = random.Random(f"{domain}:{profile_name}:cron")
        return rng.randint(minute_min, minute_max)


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_settings() -> Settings:
    load_dotenv()
    cloudflare_accounts = {
        "sweeps": (os.getenv("CLOUDFLARE_SWEEPS_API_TOKEN", ""), os.getenv("CLOUDFLARE_SWEEPS_ACCOUNT_ID", "")),
        "ecom": (os.getenv("CLOUDFLARE_ECOM_API_TOKEN", ""), os.getenv("CLOUDFLARE_ECOM_ACCOUNT_ID", "")),
    }
    whm_accounts = {
        "ecom_live": (
            os.getenv("WHM_ECOM_LIVE_BASE_URL", ""),
            os.getenv("WHM_ECOM_LIVE_USERNAME", ""),
            os.getenv("WHM_ECOM_LIVE_API_TOKEN", ""),
            os.getenv("WHM_ECOM_LIVE_PACKAGE", ""),
            os.getenv("WHM_ECOM_LIVE_CONTACT_EMAIL", ""),
        ),
        "ecom_bkp": (
            os.getenv("WHM_ECOM_BKP_BASE_URL", ""),
            os.getenv("WHM_ECOM_BKP_USERNAME", ""),
            os.getenv("WHM_ECOM_BKP_API_TOKEN", ""),
            os.getenv("WHM_ECOM_BKP_PACKAGE", ""),
            os.getenv("WHM_ECOM_BKP_CONTACT_EMAIL", ""),
        ),
        "sweeps_live": (
            os.getenv("WHM_SWEEPS_LIVE_BASE_URL", ""),
            os.getenv("WHM_SWEEPS_LIVE_USERNAME", ""),
            os.getenv("WHM_SWEEPS_LIVE_API_TOKEN", ""),
            os.getenv("WHM_SWEEPS_LIVE_PACKAGE", ""),
            os.getenv("WHM_SWEEPS_LIVE_CONTACT_EMAIL", ""),
        ),
        "sweeps_bkp": (
            os.getenv("WHM_SWEEPS_BKP_BASE_URL", ""),
            os.getenv("WHM_SWEEPS_BKP_USERNAME", ""),
            os.getenv("WHM_SWEEPS_BKP_API_TOKEN", ""),
            os.getenv("WHM_SWEEPS_BKP_PACKAGE", ""),
            os.getenv("WHM_SWEEPS_BKP_CONTACT_EMAIL", ""),
        ),
    }
    orange_accounts = {
        "sweeps_live": (os.getenv("ORANGE_SWEEPS_LIVE_USERNAME", ""), os.getenv("ORANGE_SWEEPS_LIVE_PASSWORD", "")),
        "sweeps_bkp": (os.getenv("ORANGE_SWEEPS_BKP_USERNAME", ""), os.getenv("ORANGE_SWEEPS_BKP_PASSWORD", "")),
        "ecom_live": (os.getenv("ORANGE_ECOM_LIVE_USERNAME", ""), os.getenv("ORANGE_ECOM_LIVE_PASSWORD", "")),
        "ecom_bkp": (os.getenv("ORANGE_ECOM_BKP_USERNAME", ""), os.getenv("ORANGE_ECOM_BKP_PASSWORD", "")),
    }
    return Settings(
        config_path=Path(os.getenv("OFFEROPS_CONFIG", "config.example.json")),
        state_path=Path(os.getenv("OFFEROPS_STATE", "state/jobs.json")),
        cloudflare_accounts=cloudflare_accounts,
        whm_accounts=whm_accounts,
        orange_login_url=os.getenv("ORANGE_LOGIN_URL", ""),
        orange_headless=os.getenv("ORANGE_HEADLESS", "false").lower() in {"1", "true", "yes"},
        orange_accounts=orange_accounts,
    )


def load_app_config(path: Path) -> AppConfig:
    with path.open("r", encoding="utf-8") as handle:
        return AppConfig(json.load(handle))
