from __future__ import annotations

import secrets
import string
import urllib.parse
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from ..http import JsonHttpClient
from ..models import CronSpec


@dataclass(frozen=True)
class WhmAccount:
    username: str
    password: str
    existed: bool


class WhmClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        api_token: str,
        package: str = "",
        contact_email: str = "",
        dry_run: bool = False,
    ) -> None:
        self.base_url = base_url
        self.username = username or ("root" if dry_run else "")
        self.package = package
        self.contact_email = contact_email
        self.dry_run = dry_run
        token_header = {"Authorization": f"whm {self.username}:{api_token}"} if self.username and api_token else {}
        self.http = JsonHttpClient(base_url, headers=token_header)

    def ensure_account(self, domain: str, password: str) -> WhmAccount:
        username = self.username_for_domain(domain)
        if self.dry_run:
            return WhmAccount(username=username, password=password, existed=False)
        if self.account_exists(username):
            return WhmAccount(username=username, password="", existed=True)
        params: dict[str, Any] = {
            "api.version": 1,
            "username": username,
            "domain": domain,
            "password": password,
        }
        if self.package:
            params["plan"] = self.package
        if self.contact_email:
            params["contactemail"] = self.contact_email.format(domain=domain)
        try:
            created = self.whm_api("createacct", **params)
        except RuntimeError as exc:
            if self.package and self._is_package_error(str(exc)):
                retry_params = dict(params)
                retry_params.pop("plan", None)
                created = self.whm_api("createacct", **retry_params)
            else:
                raise
        if not self.account_exists(username) and not self.domain_exists(domain):
            metadata = created.get("metadata", {}) if isinstance(created, dict) else {}
            reason = metadata.get("reason", "WHM createacct returned success, but the account was not found afterward.")
            raise RuntimeError(f"{reason} Username '{username}' for domain '{domain}' was not present after createacct.")
        return WhmAccount(username=username, password=password, existed=False)

    def account_exists(self, username: str) -> bool:
        result = self.whm_api("listaccts", **{"api.version": 1, "searchtype": "user", "search": username})
        accounts = result.get("data", {}).get("acct", [])
        return any(account.get("user") == username for account in accounts)

    def domain_exists(self, domain: str) -> bool:
        result = self.whm_api("listaccts", **{"api.version": 1, "searchtype": "domain", "search": domain})
        accounts = result.get("data", {}).get("acct", [])
        return any(account.get("domain") == domain for account in accounts)

    def create_email_account(self, cpanel_username: str, domain: str, password: str, quota_mb: int) -> dict[str, Any]:
        if self.dry_run:
            return {"email": f"support@{domain}", "quota_mb": quota_mb}
        self.uapi(cpanel_username, "Email", "add_pop", email="support", domain=domain, password=password, quota=quota_mb)
        return {"email": f"support@{domain}", "quota_mb": quota_mb}

    def email_deliverability_records(self, cpanel_username: str, domain: str) -> list[dict[str, Any]]:
        if self.dry_run:
            return [
                {"type": "TXT", "name": domain, "content": "v=spf1 include:_spf.example.invalid ~all"},
                {"type": "TXT", "name": f"default._domainkey.{domain}", "content": "v=DKIM1; k=rsa; p=dryrun"},
                {"type": "TXT", "name": f"_dmarc.{domain}", "content": "v=DMARC1; p=none"},
            ]
        records = []
        records.extend(self._dkim_records(cpanel_username, domain))
        records.extend(self._spf_records(cpanel_username, domain))
        records.extend(self._dmarc_records(cpanel_username, domain))
        return records

    def ensure_file(self, cpanel_username: str, path: str, content: str) -> dict[str, Any]:
        if self.dry_run:
            return {"path": path, "bytes": len(content)}
        target = PurePosixPath(path)
        self.uapi(
            cpanel_username,
            "Fileman",
            "save_file_content",
            dir=str(target.parent),
            file=target.name,
            content=content,
            from_charset="UTF-8",
            to_charset="UTF-8",
            fallback=0,
        )
        return {"path": path, "bytes": len(content)}

    def create_database_user(self, cpanel_username: str, domain: str, password: str) -> dict[str, Any]:
        db_name = self._prefixed_name(cpanel_username, "db", 64)
        db_user = self._prefixed_name(cpanel_username, "user", 64)
        if self.dry_run:
            return {"database": db_name, "user": db_user}
        self.uapi(cpanel_username, "Mysql", "create_database", name=db_name)
        self.uapi(cpanel_username, "Mysql", "create_user", name=db_user, password=password)
        self.uapi(cpanel_username, "Mysql", "set_privileges_on_database", user=db_user, database=db_name, privileges="ALL PRIVILEGES")
        return {"database": db_name, "user": db_user}

    def create_cron(self, cpanel_username: str, cron: CronSpec) -> dict[str, Any]:
        if self.dry_run:
            return {"cron": cron.__dict__}
        self.api2(
            cpanel_username,
            "Cron",
            "add_line",
            minute=cron.minute,
            hour=cron.hour,
            day=cron.day,
            month=cron.month,
            weekday=cron.weekday,
            command=cron.command,
        )
        return {"cron": cron.__dict__}

    def whm_api(self, function: str, **params: Any) -> dict[str, Any]:
        query = urllib.parse.urlencode(params)
        body = self.http.request("GET", f"/json-api/{function}?{query}").body
        metadata = body.get("metadata", {}) if isinstance(body, dict) else {}
        if metadata.get("result") in {0, "0", False}:
            raise RuntimeError(metadata.get("reason", f"WHM API {function} failed"))
        return body

    def uapi(self, cpanel_username: str, module: str, function: str, **params: Any) -> dict[str, Any]:
        normalized = {("pass" if key == "pass_" else key): value for key, value in params.items()}
        query = urllib.parse.urlencode(
            {
                "api.version": 1,
                "cpanel.user": cpanel_username,
                "cpanel.module": module,
                "cpanel.function": function,
                **normalized,
            }
        )
        body = self.http.request("GET", f"/json-api/uapi_cpanel?{query}").body
        metadata = body.get("metadata", {}) if isinstance(body, dict) else {}
        if metadata.get("result") in {0, "0", False}:
            raise RuntimeError(metadata.get("reason", f"WHM UAPI {module}::{function} failed"))
        result = body.get("data", {}).get("uapi", {}) if isinstance(body, dict) else {}
        if result.get("status") in {0, "0", False}:
            errors = result.get("errors") or result.get("messages") or [result.get("statusmsg", "Unknown cPanel error")]
            raise RuntimeError("; ".join(str(item) for item in errors if item))
        return result

    def api2(self, cpanel_username: str, module: str, function: str, **params: Any) -> dict[str, Any]:
        query = urllib.parse.urlencode(
            {
                "cpanel_jsonapi_user": cpanel_username,
                "cpanel_jsonapi_apiversion": 2,
                "cpanel_jsonapi_module": module,
                "cpanel_jsonapi_func": function,
                **params,
            }
        )
        body = self.http.request("GET", f"/json-api/cpanel?{query}").body
        if isinstance(body, dict) and body.get("cpanelresult", {}).get("error"):
            raise RuntimeError(str(body["cpanelresult"]["error"]))
        return body

    def _dkim_records(self, cpanel_username: str, domain: str) -> list[dict[str, Any]]:
        result = self.uapi(cpanel_username, "EmailAuth", "validate_current_dkims", domain=domain)
        records = []
        for item in result.get("data", []):
            content = item.get("record") or item.get("expected")
            name = item.get("domain")
            if content and name:
                records.append({"type": "TXT", "name": str(name), "content": str(content)})
        return records

    def _spf_records(self, cpanel_username: str, domain: str) -> list[dict[str, Any]]:
        result = self.uapi(cpanel_username, "EmailAuth", "validate_current_spfs", domain=domain)
        records = []
        for item in result.get("data", []):
            name = item.get("domain")
            if not name:
                continue
            content = item.get("record")
            if not content:
                expected = str(item.get("expected", "")).strip()
                mechanisms = ["+a", "+mx"]
                if expected:
                    mechanisms.append(expected if expected.startswith("+") else f"+{expected}")
                content = f"v=spf1 {' '.join(mechanisms)} ~all"
            records.append({"type": "TXT", "name": str(name), "content": str(content)})
        return records

    def _dmarc_records(self, cpanel_username: str, domain: str) -> list[dict[str, Any]]:
        result = self.uapi(cpanel_username, "EmailAuth", "validate_current_dmarcs", domain=domain)
        records = []
        for item in result.get("data", []):
            content = item.get("record") or item.get("suggested")
            name = item.get("subdomain") or f"_dmarc.{domain}"
            if content and name:
                records.append({"type": "TXT", "name": str(name), "content": str(content)})
        return records

    @staticmethod
    def random_password(length: int = 16) -> str:
        alphabet = string.ascii_letters + string.digits + "!@#$%^*_-[](),"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def cpanel_login_url(whm_base_url: str) -> str:
        parsed = urllib.parse.urlparse(whm_base_url)
        port = 2083 if parsed.port == 2087 else parsed.port
        netloc = parsed.hostname or ""
        if port:
            netloc = f"{netloc}:{port}"
        return urllib.parse.urlunparse((parsed.scheme or "https", netloc, "", "", "", ""))

    @staticmethod
    def username_for_domain(domain: str) -> str:
        base = "".join(ch for ch in domain.split(".")[0].lower() if ch.isalnum())
        if not base or not base[0].isalpha():
            base = f"a{base}"
        return base[:16]

    @staticmethod
    def _prefixed_name(username: str, suffix: str, max_len: int) -> str:
        separator = "_" if username else ""
        available_for_prefix = max_len - len(separator) - len(suffix)
        prefix = username[: max(0, available_for_prefix)]
        return f"{prefix}{separator}{suffix}"[:max_len]

    @staticmethod
    def _is_package_error(message: str) -> bool:
        lowered = message.lower()
        return "unable to use package" in lowered or "package exists" in lowered or "reseller restrictions" in lowered
