from __future__ import annotations

import hashlib
import secrets
import string
import urllib.parse
from typing import Any

from ..http import JsonHttpClient
from ..models import CronSpec


class CpanelClient:
    def __init__(self, base_url: str, username: str, api_token: str, dry_run: bool = False) -> None:
        self.username = username or ("cpaneluser" if dry_run else "")
        self.dry_run = dry_run
        token_header = {"Authorization": f"cpanel {self.username}:{api_token}"} if self.username and api_token else {}
        self.http = JsonHttpClient(base_url, headers=token_header)

    def create_ftp_account(self, domain: str, password: str, quota_mb: int, homedir: str) -> dict[str, Any]:
        user = self._safe_name(domain, "ftp")
        if self.dry_run:
            return {"user": user, "homedir": homedir, "quota_mb": quota_mb}
        return self.uapi("Ftp", "add_ftp", user=user, pass_=password, quota=quota_mb, homedir=homedir)

    def create_email_account(self, domain: str, password: str, quota_mb: int) -> dict[str, Any]:
        if self.dry_run:
            return {"email": f"support@{domain}", "quota_mb": quota_mb}
        return self.uapi("Email", "add_pop", email="support", domain=domain, password=password, quota=quota_mb)

    def email_deliverability_records(self, domain: str) -> list[dict[str, Any]]:
        if self.dry_run:
            return [
                {"type": "TXT", "name": domain, "content": "v=spf1 include:_spf.example.invalid ~all"},
                {"type": "TXT", "name": f"default._domainkey.{domain}", "content": "v=DKIM1; k=rsa; p=dryrun"},
                {"type": "TXT", "name": f"_dmarc.{domain}", "content": "v=DMARC1; p=none"},
            ]
        result = self.uapi("Email", "validate_current_dkims", domain=domain)
        records = []
        for item in result.get("data", {}).get("payload", []):
            records.append({"type": "TXT", "name": item["name"], "content": item["value"]})
        return records

    def ensure_file(self, path: str, content: str) -> dict[str, Any]:
        if self.dry_run:
            return {"path": path, "bytes": len(content)}
        return self.uapi("Fileman", "save_file_content", file=path, content=content)

    def create_database_user(self, domain: str, password: str) -> dict[str, Any]:
        name = self._db_slug(domain)
        db_name = self._prefixed_name(self.username, name, 64)
        db_user = self._prefixed_name(self.username, hashlib.sha1(domain.encode("utf-8")).hexdigest()[:6], 16)
        if self.dry_run:
            return {"database": db_name, "user": db_user}
        self.uapi("Mysql", "create_database", name=db_name)
        self.uapi("Mysql", "create_user", name=db_user, password=password)
        self.uapi("Mysql", "set_privileges_on_database", user=db_user, database=db_name, privileges="ALL PRIVILEGES")
        return {"database": db_name, "user": db_user}

    def create_cron(self, cron: CronSpec) -> dict[str, Any]:
        if self.dry_run:
            return {"cron": cron.__dict__}
        return self.uapi(
            "Cron",
            "add_line",
            minute=cron.minute,
            hour=cron.hour,
            day=cron.day,
            month=cron.month,
            weekday=cron.weekday,
            command=cron.command,
        )

    def uapi(self, module: str, function: str, **params: Any) -> dict[str, Any]:
        normalized = {("pass" if key == "pass_" else key): value for key, value in params.items()}
        query = urllib.parse.urlencode(normalized)
        return self.http.request("GET", f"/execute/{module}/{function}?{query}").body

    @staticmethod
    def random_password(length: int = 16) -> str:
        alphabet = string.ascii_letters + string.digits + "!@#$%^*_-[](),"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def _safe_name(domain: str, suffix: str) -> str:
        base = "".join(ch for ch in domain.split(".")[0].lower() if ch.isalnum())
        return f"{base}{suffix}"[:16]

    @staticmethod
    def _db_slug(domain: str) -> str:
        base = "".join(ch for ch in domain.split(".")[0].lower() if ch.isalnum())
        digest = hashlib.sha1(domain.encode("utf-8")).hexdigest()[:5]
        return f"{base[:8]}{digest}"

    @staticmethod
    def _prefixed_name(username: str, suffix: str, max_len: int) -> str:
        separator = "_" if username else ""
        available_for_prefix = max_len - len(separator) - len(suffix)
        prefix = username[: max(0, available_for_prefix)]
        return f"{prefix}{separator}{suffix}"[:max_len]
