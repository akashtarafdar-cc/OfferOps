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
        canonical_name = self.canonical_profile_name(name)
        if canonical_name not in profiles:
            raise KeyError(f"Unknown profile '{name}'. Add it under profiles in config.")
        return dict(profiles[canonical_name])

    def profile_names(self) -> list[str]:
        return list(self.raw.get("profiles", {}).keys())

    def profile_summaries(self) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for name in self.profile_names():
            profile = self.profile(name)
            summaries.append(
                {
                    "name": name,
                    "kind": str(profile.get("kind", "")),
                    "servers": [str(item) for item in profile.get("servers", [])],
                    "cloudflare_account": str(profile.get("cloudflare_account", "")),
                    "whm_account": str(profile.get("whm_account", "")),
                }
            )
        return summaries

    def server_choices_for_kind(self, kind: str) -> list[str]:
        canonical_kind = str(kind).strip().lower()
        servers: list[str] = []
        for summary in self.profile_summaries():
            if summary["kind"] != canonical_kind:
                continue
            for server in summary["servers"]:
                if server not in servers:
                    servers.append(server)
        return servers

    def resolve_profile_for_kind_server(self, kind: str, server: str) -> str:
        canonical_kind = str(kind).strip().lower()
        canonical_server = self.canonical_profile_name(server).replace(" ", "-")
        matches = [
            summary["name"]
            for summary in self.profile_summaries()
            if summary["kind"] == canonical_kind
            and canonical_server in [self.canonical_profile_name(item).replace(" ", "-") for item in summary["servers"]]
        ]
        if not matches:
            raise KeyError(f"No profile matches kind '{kind}' and server '{server}'.")
        if len(matches) > 1:
            exact_name = self.canonical_profile_name(f"{canonical_kind}-{canonical_server}")
            for match in matches:
                if self.canonical_profile_name(match) == exact_name:
                    return match
        return matches[0]

    @staticmethod
    def canonical_profile_name(name: str) -> str:
        return "-".join(str(name).strip().lower().replace("_", " ").split())

    def cloudflare_account_for(self, profile_name: str) -> str:
        return str(self.profile(profile_name)["cloudflare_account"])

    def whm_account_for(self, profile_name: str) -> str:
        return str(self.profile(profile_name)["whm_account"])

    def cloudflare_bot_fight_mode_enabled(self) -> bool:
        return bool(self.defaults.get("cloudflare_bot_fight_mode", True))

    def orange_account_names_for(self, profile_name: str) -> list[str]:
        account_group = self.cloudflare_account_for(profile_name).strip().lower()
        profile = self.profile(profile_name)
        configured = profile.get("orange_accounts", [])
        if isinstance(configured, list) and configured:
            preferred = [str(item).strip() for item in configured if str(item).strip()]
        else:
            preferred = [name for name in self._default_orange_account_order() if name.startswith(f"{account_group}_")]

        ordered: list[str] = []
        for name in preferred + self._default_orange_account_order():
            if name not in ordered:
                ordered.append(name)
        return ordered

    def dns_records_for(self, profile_name: str, domain: str) -> list[DnsRecord]:
        profile = self.profile(profile_name)
        ttl = int(self.defaults.get("dns_ttl", 1))
        server_ip = self._server_ip_for(profile)
        return [
            DnsRecord.from_dict(self._render_record_template(item, domain, server_ip), domain, ttl)
            for item in profile.get("dns_records", [])
        ]

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

    def server_ip_for(self, profile_name: str) -> str:
        profile = self.profile(profile_name)
        return self._server_ip_for(profile)

    @staticmethod
    def _stable_random_interval(domain: str, profile_name: str, minute_min: int, minute_max: int) -> int:
        if minute_min > minute_max:
            raise ValueError("cron minute_min cannot be greater than minute_max")
        rng = random.Random(f"{domain}:{profile_name}:cron")
        return rng.randint(minute_min, minute_max)

    @staticmethod
    def _server_ip_for(profile: dict[str, Any]) -> str:
        if "server_ip" in profile:
            return str(profile["server_ip"])
        env_name = str(profile.get("server_ip_env", "")).strip()
        if env_name:
            value = os.getenv(env_name, "").strip()
            if not value:
                raise ValueError(f"Environment variable '{env_name}' is required for this profile's DNS records.")
            return value
        return ""

    @staticmethod
    def _render_record_template(record: dict[str, Any], domain: str, server_ip: str) -> dict[str, Any]:
        rendered: dict[str, Any] = {}
        for key, value in record.items():
            if isinstance(value, str):
                rendered[key] = value.format(domain=domain, server_ip=server_ip)
            else:
                rendered[key] = value
        return rendered

    @staticmethod
    def _default_orange_account_order() -> list[str]:
        return [
            "sweeps_live",
            "sweeps_bkp",
            "sweeps_live_2",
            "sweeps_bkp_2",
            "sweeps_live_3",
            "sweeps_live_4",
            "ecom_live",
            "ecom_bkp",
        ]


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
        "sweeps_live_2": (
            os.getenv("WHM_SWEEPS_LIVE_2_BASE_URL", ""),
            os.getenv("WHM_SWEEPS_LIVE_2_USERNAME", ""),
            os.getenv("WHM_SWEEPS_LIVE_2_API_TOKEN", ""),
            os.getenv("WHM_SWEEPS_LIVE_2_PACKAGE", ""),
            os.getenv("WHM_SWEEPS_LIVE_2_CONTACT_EMAIL", ""),
        ),
        "sweeps_bkp_2": (
            os.getenv("WHM_SWEEPS_BKP_2_BASE_URL", ""),
            os.getenv("WHM_SWEEPS_BKP_2_USERNAME", ""),
            os.getenv("WHM_SWEEPS_BKP_2_API_TOKEN", ""),
            os.getenv("WHM_SWEEPS_BKP_2_PACKAGE", ""),
            os.getenv("WHM_SWEEPS_BKP_2_CONTACT_EMAIL", ""),
        ),
        "sweeps_live_3": (
            os.getenv("WHM_SWEEPS_LIVE_3_BASE_URL", ""),
            os.getenv("WHM_SWEEPS_LIVE_3_USERNAME", ""),
            os.getenv("WHM_SWEEPS_LIVE_3_API_TOKEN", ""),
            os.getenv("WHM_SWEEPS_LIVE_3_PACKAGE", ""),
            os.getenv("WHM_SWEEPS_LIVE_3_CONTACT_EMAIL", ""),
        ),
        "sweeps_live_4": (
            os.getenv("WHM_SWEEPS_LIVE_4_BASE_URL", ""),
            os.getenv("WHM_SWEEPS_LIVE_4_USERNAME", ""),
            os.getenv("WHM_SWEEPS_LIVE_4_API_TOKEN", ""),
            os.getenv("WHM_SWEEPS_LIVE_4_PACKAGE", ""),
            os.getenv("WHM_SWEEPS_LIVE_4_CONTACT_EMAIL", ""),
        ),
    }
    orange_accounts = {
        "sweeps_live": (os.getenv("ORANGE_SWEEPS_LIVE_USERNAME", ""), os.getenv("ORANGE_SWEEPS_LIVE_PASSWORD", "")),
        "sweeps_bkp": (os.getenv("ORANGE_SWEEPS_BKP_USERNAME", ""), os.getenv("ORANGE_SWEEPS_BKP_PASSWORD", "")),
        "sweeps_live_2": (os.getenv("ORANGE_SWEEPS_LIVE_2_USERNAME", ""), os.getenv("ORANGE_SWEEPS_LIVE_2_PASSWORD", "")),
        "sweeps_bkp_2": (os.getenv("ORANGE_SWEEPS_BKP_2_USERNAME", ""), os.getenv("ORANGE_SWEEPS_BKP_2_PASSWORD", "")),
        "sweeps_live_3": (os.getenv("ORANGE_SWEEPS_LIVE_3_USERNAME", ""), os.getenv("ORANGE_SWEEPS_LIVE_3_PASSWORD", "")),
        "sweeps_live_4": (os.getenv("ORANGE_SWEEPS_LIVE_4_USERNAME", ""), os.getenv("ORANGE_SWEEPS_LIVE_4_PASSWORD", "")),
        "ecom_live": (os.getenv("ORANGE_ECOM_LIVE_USERNAME", ""), os.getenv("ORANGE_ECOM_LIVE_PASSWORD", "")),
        "ecom_bkp": (os.getenv("ORANGE_ECOM_BKP_USERNAME", ""), os.getenv("ORANGE_ECOM_BKP_PASSWORD", "")),
    }
    return Settings(
        config_path=Path(os.getenv("OFFEROPS_CONFIG", "config.json")),
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
