from __future__ import annotations

from dataclasses import asdict
from typing import Callable

from .config import AppConfig, Settings
from .http import HttpError
from .models import DnsRecord, DomainJob, JobResult, StepResult, StepStatus
from .providers.cloudflare import CloudflareClient
from .providers.orange_browser import OrangeAccount, OrangeBrowserClient
from .providers.whm import WhmClient
from .state import StateStore, serialize_result, step_from_exception


class OfferProvisioner:
    def __init__(
        self,
        settings: Settings,
        config: AppConfig,
        state: StateStore,
        dry_run: bool = False,
        use_orange_browser: bool = False,
        progress_callback: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.settings = settings
        self.config = config
        self.state = state
        self.dry_run = dry_run
        self.use_orange_browser = use_orange_browser
        self.progress_callback = progress_callback

    def run(self, job: DomainJob) -> JobResult:
        result = JobResult(domain=job.domain, profile=job.profile, status=StepStatus.RUNNING)
        self._publish(result)
        try:
            profile = self.config.profile(job.profile)
        except Exception as exc:
            result.add(step_from_exception("load-profile", exc))
            self._publish(result)
            return result

        offer_path = job.resolved_offer_path()
        if not offer_path:
            result.add(StepResult(name="offer-path", status=StepStatus.FAILED, message="CSV row must include offer_path, offer_url, or offer with a path like v1/msrack."))
            self._publish(result)
            return result

        zone_id = ""
        nameservers: list[str] = []
        cloudflare = self._cloudflare_for(job.profile)
        whm = self._whm_for(job.profile)
        account_password = WhmClient.random_password()
        cpanel_username = ""
        account_existed = False
        document_root = self.config.document_root_for(job.domain)
        mail_password = WhmClient.random_password()
        db_password = WhmClient.random_password()
        database_info: dict[str, object] = {}
        support_email = f"support@{job.domain}"
        server_ip = self.config.server_ip_for(job.profile)
        email_url = f"{job.domain}/webmail"

        steps = [
            ("cloudflare-zone", lambda: cloudflare.ensure_zone(job.domain, self.config.defaults.get("cloudflare_plan", "free"))),
            ("cloudflare-bot-fight-mode", lambda: cloudflare.set_bot_fight_mode(zone_id, self.config.cloudflare_bot_fight_mode_enabled())),
            ("orange-nameservers", lambda: self._orange_nameserver_step(job.domain, job.profile, nameservers)),
            ("cloudflare-dns", lambda: self._upsert_records(cloudflare, zone_id, job.domain, self.config.dns_records_for(job.profile, job.domain))),
            ("whm-account", lambda: whm.ensure_account(job.domain, account_password)),
            (
                "cpanel-support-email",
                lambda: whm.create_email_account(
                    cpanel_username,
                    job.domain,
                    mail_password,
                    int(self.config.defaults.get("support_mail_quota_mb", 1024)),
                ),
            ),
            ("email-deliverability", lambda: self._sync_email_records(whm, cpanel_username, cloudflare, zone_id, job.domain)),
            ("files", lambda: self._write_default_files(whm, cpanel_username, document_root)),
            ("database", lambda: whm.create_database_user(cpanel_username, job.domain, db_password)),
            ("cron", lambda: whm.create_cron(cpanel_username, self.config.cron_for(job.domain, cpanel_username, job.profile, offer_path))),
        ]

        for name, action in steps:
            self._update_step(result, StepResult(name=name, status=StepStatus.RUNNING, message=self._step_message(name)))
            try:
                data = action()
                if name == "cloudflare-zone":
                    zone_id = str(data["id"])
                    nameservers = self._preferred_nameservers(data)
                if name == "whm-account":
                    cpanel_username = data.username
                    account_existed = bool(data.existed)
                if name == "database" and isinstance(data, dict):
                    database_info = data
                self._update_step(result, StepResult(name=name, status=StepStatus.DONE, message=self._step_message(name), data=self._safe_data(data)))
            except Exception as exc:
                if name == "cloudflare-bot-fight-mode" and self._should_skip_bot_fight_mode(exc):
                    self._update_step(
                        result,
                        StepResult(
                            name=name,
                            status=StepStatus.SKIPPED,
                            message=f"Skipping Bot Fight Mode: {exc}",
                        )
                    )
                    continue
                self._update_step(result, step_from_exception(name, exc))
                break

        result.credentials = (
            {
                "domain": job.domain,
                "cpanel_username": cpanel_username,
                "cpanel_account_password": "" if account_existed else account_password,
                "cpanel_account_password_note": "Not shown because the cPanel account already existed."
                if account_existed
                else "Shown because this run created the cPanel account.",
                "support_email": support_email,
                "email_url": email_url,
                "support_email_password": mail_password,
                "database_name": str(database_info.get("database", "")),
                "database_user": str(database_info.get("user", "")),
                "database_user_password": db_password,
                "nameservers": nameservers,
                "server_ip": server_ip,
            }
            if result.status != StepStatus.FAILED
            else {}
        )
        self._update_step(
            result,
            StepResult(
                name="secrets",
                status=StepStatus.DONE if result.status != StepStatus.FAILED else StepStatus.SKIPPED,
                message="Generated credentials were saved to a local file.",
                data={
                    "credentials_file": str(
                        self.state.save_credentials(
                            job.domain,
                            {
                                "domain": job.domain,
                                "cpanel_username": cpanel_username,
                                "cpanel_account_password": "" if account_existed else account_password,
                                "cpanel_account_password_note": "Not shown because the cPanel account already existed."
                                if account_existed
                                else "Shown because this run created the cPanel account.",
                                "support_email": support_email,
                                "email_url": email_url,
                                "support_email_password": mail_password,
                                "database_name": str(database_info.get("database", "")),
                                "database_user": str(database_info.get("user", "")),
                                "database_user_password": db_password,
                                "profile_kind": profile.get("kind", ""),
                                "servers": profile.get("servers", []),
                                "offer_path": offer_path,
                                "document_root": document_root,
                                "nameservers": nameservers,
                                "server_ip": server_ip,
                            },
                        )
                    ),
                    "domain": job.domain,
                    "cpanel_username": cpanel_username,
                    "support_email": support_email,
                    "email_url": email_url,
                    "database_name": str(database_info.get("database", "")),
                    "database_user": str(database_info.get("user", "")),
                    "document_root": document_root,
                    "nameservers": nameservers,
                    "server_ip": server_ip,
                }
                if result.status != StepStatus.FAILED
                else {},
            )
        )
        if result.status != StepStatus.FAILED:
            result.status = StepStatus.DONE
        self._publish(result)
        return result

    def run_orange_nameserver_update(self, domain: str, profile_name: str) -> dict[str, object]:
        nameservers = self._resolve_nameservers(domain, profile_name)
        return self._orange_nameserver_step(domain, profile_name, nameservers)

    def _cloudflare_for(self, profile_name: str) -> CloudflareClient:
        account_name = self.config.cloudflare_account_for(profile_name)
        if account_name not in self.settings.cloudflare_accounts:
            raise KeyError(f"Unknown Cloudflare account '{account_name}' for profile '{profile_name}'.")
        api_token, account_id = self.settings.cloudflare_accounts[account_name]
        return CloudflareClient(api_token, account_id, dry_run=self.dry_run)

    def _whm_for(self, profile_name: str) -> WhmClient:
        account_name = self.config.whm_account_for(profile_name)
        if account_name not in self.settings.whm_accounts:
            raise KeyError(f"Unknown WHM account '{account_name}' for profile '{profile_name}'.")
        base_url, username, api_token, package, contact_email = self.settings.whm_accounts[account_name]
        return WhmClient(base_url, username, api_token, package=package, contact_email=contact_email, dry_run=self.dry_run)

    def _upsert_records(self, cloudflare: CloudflareClient, zone_id: str, domain: str, records: list[DnsRecord]) -> dict[str, object]:
        return {"records": [cloudflare.upsert_dns_record(zone_id, record, domain) for record in records]}

    def _orange_nameserver_step(self, domain: str, profile_name: str, nameservers: list[str]) -> dict[str, object]:
        if self.use_orange_browser:
            return self._orange_browser(profile_name).update_nameservers(domain, nameservers)
        return {
            "domain": domain,
            "nameservers": nameservers,
            "manual_action": "Update this domain's nameservers in orange hosting/registrar manually.",
        }

    def _orange_browser(self, profile_name: str) -> OrangeBrowserClient:
        allowed_accounts = self.config.orange_account_names_for(profile_name)
        accounts = [
            OrangeAccount(name=name, username=username, password=password)
            for name in allowed_accounts
            if name in self.settings.orange_accounts
            for username, password in [self.settings.orange_accounts[name]]
        ]
        return OrangeBrowserClient(
            login_url=self.settings.orange_login_url,
            accounts=accounts,
            headless=self.settings.orange_headless,
            dry_run=self.dry_run,
        )

    def _sync_email_records(self, whm: WhmClient, cpanel_username: str, cloudflare: CloudflareClient, zone_id: str, domain: str) -> dict[str, object]:
        records = [
            DnsRecord(type=item["type"], name=item["name"], content=item["content"], ttl=int(self.config.defaults.get("dns_ttl", 1)))
            for item in whm.email_deliverability_records(cpanel_username, domain)
        ]
        return {"records": [cloudflare.upsert_dns_record(zone_id, record, domain) for record in records]}

    def _write_default_files(self, whm: WhmClient, cpanel_username: str, document_root: str) -> dict[str, object]:
        robots = str(self.config.defaults.get("robots_txt", "User-agent: *\nDisallow:\n"))
        info = str(self.config.defaults.get("info_php", "<?php phpinfo();\n"))
        return {
            "robots": whm.ensure_file(cpanel_username, f"{document_root}/robots.txt", robots),
            "info": whm.ensure_file(cpanel_username, f"{document_root}/info.php", info),
        }

    def _safe_data(self, data: object) -> dict[str, object]:
        if isinstance(data, dict):
            return {key: value for key, value in data.items() if "password" not in key.lower()}
        if hasattr(data, "__dataclass_fields__"):
            return {key: value for key, value in asdict(data).items() if "password" not in key.lower()}
        return {"value": str(data)}

    def _resolve_nameservers(self, domain: str, profile_name: str) -> list[str]:
        zone = self._cloudflare_for(profile_name).ensure_zone(domain, self.config.defaults.get("cloudflare_plan", "free"))
        return self._preferred_nameservers(zone)

    def _publish(self, result: JobResult) -> None:
        self.state.save_result(result)
        if self.progress_callback is not None:
            self.progress_callback(serialize_result(result, include_credentials=True))

    def _update_step(self, result: JobResult, step: StepResult) -> None:
        result.add(step)
        self._publish(result)

    @staticmethod
    def _step_message(name: str) -> str:
        messages = {
            "cloudflare-zone": "Preparing the domain zone.",
            "cloudflare-bot-fight-mode": "Applying security settings.",
            "orange-nameservers": "Updating nameservers in Orange.",
            "cloudflare-dns": "Publishing DNS records.",
            "whm-account": "Preparing the hosting account.",
            "cpanel-support-email": "Creating the support mailbox.",
            "email-deliverability": "Publishing email deliverability records.",
            "files": "Uploading starter files.",
            "database": "Creating the database.",
            "cron": "Scheduling recurring tasks.",
            "secrets": "Saving the final credentials.",
        }
        return messages.get(name, name)

    @staticmethod
    def _preferred_nameservers(zone_data: object) -> list[str]:
        if isinstance(zone_data, dict):
            live_nameservers = [str(item) for item in zone_data.get("name_servers", []) if str(item).strip()]
            if live_nameservers:
                return live_nameservers
        raise ValueError("Cloudflare did not return zone nameservers for this domain.")

    @staticmethod
    def _should_skip_bot_fight_mode(exc: Exception) -> bool:
        if isinstance(exc, HttpError) and exc.response is not None:
            return int(exc.response.status) in {401, 403, 404}
        return False
