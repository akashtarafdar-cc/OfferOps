from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class OrangeAutomationNotConfigured(RuntimeError):
    pass


@dataclass(frozen=True)
class OrangeAccount:
    name: str
    username: str
    password: str


class OrangeBrowserClient:
    """Browser automation for Orange nameserver updates.

    This class is intentionally selector-driven. Orange has no API, so the
    exact selectors must match your account UI after we inspect screenshots or
    record a Playwright trace.
    """

    SELECTORS = {
        "username": "input[name='username']",
        "password": "input[name='password']",
        "login_submit": "button[type='submit']",
        "domain_search": "input[name='domain']",
        "domain_result": "text={domain}",
        "nameserver_1": "input[name='ns1']",
        "nameserver_2": "input[name='ns2']",
        "save_nameservers": "button[type='submit']",
    }

    def __init__(self, login_url: str, accounts: list[OrangeAccount], headless: bool = False, dry_run: bool = False) -> None:
        self.login_url = login_url
        self.accounts = accounts
        self.headless = headless
        self.dry_run = dry_run

    def update_nameservers(self, domain: str, nameservers: list[str]) -> dict[str, Any]:
        if self.dry_run:
            return {
                "domain": domain,
                "searched_accounts": [account.name for account in self.accounts if account.username],
                "matched_account": "dry-run",
                "nameservers": nameservers,
            }
        if not self.login_url:
            raise OrangeAutomationNotConfigured("ORANGE_LOGIN_URL is required for browser automation.")
        if len(nameservers) < 2:
            raise OrangeAutomationNotConfigured("At least two nameservers are required.")

        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise OrangeAutomationNotConfigured("Install Playwright first: pip install playwright && playwright install chromium") from exc

        attempted: list[str] = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.headless)
            try:
                for account in self.accounts:
                    if not account.username or not account.password:
                        continue
                    attempted.append(account.name)
                    page = browser.new_page()
                    try:
                        self._login(page, account)
                        if not self._open_domain(page, domain, PlaywrightTimeoutError):
                            page.close()
                            continue
                        self._save_nameservers(page, nameservers)
                        page.close()
                        return {
                            "domain": domain,
                            "searched_accounts": attempted,
                            "matched_account": account.name,
                            "nameservers": nameservers,
                        }
                    except PlaywrightTimeoutError:
                        page.close()
                        continue
            finally:
                browser.close()
        raise OrangeAutomationNotConfigured(f"Domain '{domain}' was not found in Orange accounts: {', '.join(attempted)}")

    def _login(self, page: Any, account: OrangeAccount) -> None:
        page.goto(self.login_url)
        page.fill(self.SELECTORS["username"], account.username)
        page.fill(self.SELECTORS["password"], account.password)
        page.click(self.SELECTORS["login_submit"])
        page.wait_for_load_state("networkidle")

    def _open_domain(self, page: Any, domain: str, timeout_error: type[Exception]) -> bool:
        page.fill(self.SELECTORS["domain_search"], domain)
        page.keyboard.press("Enter")
        try:
            page.locator(self.SELECTORS["domain_result"].format(domain=domain)).first.click(timeout=8000)
            page.wait_for_load_state("networkidle")
            return True
        except timeout_error:
            return False

    def _save_nameservers(self, page: Any, nameservers: list[str]) -> None:
        page.fill(self.SELECTORS["nameserver_1"], nameservers[0])
        page.fill(self.SELECTORS["nameserver_2"], nameservers[1])
        page.click(self.SELECTORS["save_nameservers"])
        page.wait_for_load_state("networkidle")

