from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


class OrangeAutomationNotConfigured(RuntimeError):
    pass


@dataclass(frozen=True)
class OrangeAccount:
    name: str
    username: str
    password: str


class OrangeBrowserClient:
    """Selenium-based browser automation for Orange nameserver updates."""

    DOMAINS_PATH = "/clientarea.php?action=domains"
    CONNECTION_RESET_HINT = (
        "Orange reset the browser connection while loading the page. "
        "Try again in a moment, verify the Orange login URL, or update the nameservers manually."
    )

    SELECTORS: dict[str, list[tuple[str, str]]] = {
        "username": [
            ("css selector", "input[name='username']"),
            ("css selector", "input[name='email']"),
            ("css selector", "input[type='email']"),
            ("xpath", "//input[contains(@placeholder, 'Email') or contains(@placeholder, 'Username')]"),
        ],
        "password": [
            ("css selector", "input[name='password']"),
            ("css selector", "input[type='password']"),
        ],
        "login_submit": [
            ("css selector", "button[type='submit']"),
            ("xpath", "//button[contains(., 'Login') or contains(., 'Sign in') or contains(., 'Log in')]"),
            ("xpath", "//input[@type='submit']"),
        ],
        "domain_search": [
            ("css selector", "div.dataTables_filter input[type='search']"),
            ("xpath", "//div[contains(@class, 'dataTables_filter')]//input[@type='search']"),
            ("xpath", "//h1[contains(., 'My Domains')]/following::input[@type='search'][1]"),
        ],
        "domain_result": [
            ("xpath", "//table//tr[.//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{domain}')]]"),
        ],
        "domain_actions_toggle": [
            ("xpath", ".//button[contains(@class, 'dropdown-toggle')]"),
            ("xpath", ".//*[self::button or self::a][contains(@class, 'dropdown-toggle')]"),
            ("xpath", ".//button[contains(@aria-haspopup, 'true')]"),
        ],
        "manage_nameservers": [
            ("xpath", "//a[contains(., 'Manage Nameservers')]"),
            ("xpath", "//li//a[contains(., 'Manage Nameservers')]"),
        ],
        "custom_nameservers_tab": [
            ("xpath", "//button[contains(., 'Nameserver')]"),
            ("xpath", "//a[contains(., 'Nameserver')]"),
            ("xpath", "//label[contains(., 'Custom nameserver')]"),
        ],
        "use_custom_nameservers": [
            ("xpath", "//input[@type='radio' and @value='custom']"),
            ("xpath", "//label[contains(., 'Use custom nameservers')]/preceding-sibling::input[@type='radio']"),
            ("xpath", "//label[contains(., 'Use custom nameservers')]"),
        ],
        "nameserver_1": [
            ("css selector", "input[name='ns1']"),
            ("css selector", "input[name='nameserver1']"),
            ("css selector", "input[name='nameserver_1']"),
            ("xpath", "//label[contains(., 'Nameserver 1')]/following::input[1]"),
            ("xpath", "(//input[contains(@name, 'ns') or contains(@id, 'ns')])[1]"),
        ],
        "nameserver_2": [
            ("css selector", "input[name='ns2']"),
            ("css selector", "input[name='nameserver2']"),
            ("css selector", "input[name='nameserver_2']"),
            ("xpath", "//label[contains(., 'Nameserver 2')]/following::input[1]"),
            ("xpath", "(//input[contains(@name, 'ns') or contains(@id, 'ns')])[2]"),
        ],
        "nameserver_3": [
            ("css selector", "input[name='ns3']"),
            ("css selector", "input[name='nameserver3']"),
            ("css selector", "input[name='nameserver_3']"),
            ("xpath", "//label[contains(., 'Nameserver 3')]/following::input[1]"),
            ("xpath", "(//input[contains(@name, 'ns') or contains(@id, 'ns')])[3]"),
        ],
        "nameserver_4": [
            ("css selector", "input[name='ns4']"),
            ("css selector", "input[name='nameserver4']"),
            ("css selector", "input[name='nameserver_4']"),
            ("xpath", "//label[contains(., 'Nameserver 4')]/following::input[1]"),
            ("xpath", "(//input[contains(@name, 'ns') or contains(@id, 'ns')])[4]"),
        ],
        "nameserver_5": [
            ("css selector", "input[name='ns5']"),
            ("css selector", "input[name='nameserver5']"),
            ("css selector", "input[name='nameserver_5']"),
            ("xpath", "//label[contains(., 'Nameserver 5')]/following::input[1]"),
            ("xpath", "(//input[contains(@name, 'ns') or contains(@id, 'ns')])[5]"),
        ],
        "save_nameservers": [
            ("xpath", "//button[normalize-space()='Change Nameservers']"),
            ("xpath", "//form//button[normalize-space()='Change Nameservers']"),
            ("css selector", "button.btn.btn-primary"),
            ("xpath", "//button[contains(., 'Save') or contains(., 'Update') or contains(., 'Change')]"),
            ("xpath", "//input[@type='submit']"),
        ],
        "nameserver_submit_success": [
            ("css selector", "div.alert.alert-success"),
            ("xpath", "//*[contains(@class, 'alert-success')]"),
            ("xpath", "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'nameserver') and contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'updated')]"),
            ("xpath", "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'changes saved')]"),
        ],
        "post_login_marker": [
            ("xpath", "//a[contains(., 'Logout')]"),
            ("xpath", "//h1[contains(., 'Welcome Back')]"),
            ("xpath", "//a[contains(., 'My Domains')]"),
        ],
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

        attempted: list[str] = []
        domain_key = domain.strip().lower()
        for account in self.accounts:
            if not account.username or not account.password:
                continue
            attempted.append(account.name)
            driver = self._build_driver()
            try:
                self._login(driver, account)
                if not self._open_domain(driver, domain_key):
                    continue
                self._save_nameservers(driver, nameservers)
                return {
                    "domain": domain,
                    "searched_accounts": attempted,
                    "matched_account": account.name,
                    "nameservers": nameservers,
                }
            except Exception as exc:
                if self._is_connection_reset_error(exc):
                    raise OrangeAutomationNotConfigured(self.CONNECTION_RESET_HINT) from exc
                raise
            finally:
                driver.quit()
        raise OrangeAutomationNotConfigured(f"Domain '{domain}' was not found in Orange accounts: {', '.join(attempted)}")

    def _build_driver(self) -> Any:
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options as ChromeOptions
        except ImportError as exc:
            raise OrangeAutomationNotConfigured("Install Selenium first: pip install selenium") from exc

        options = ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1440,1200")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        try:
            return webdriver.Chrome(options=options)
        except Exception as exc:
            raise OrangeAutomationNotConfigured(
                "Unable to start Chrome WebDriver. Install Google Chrome/Chromium and ensure Selenium Manager or chromedriver can launch it."
            ) from exc

    def _login(self, driver: Any, account: OrangeAccount) -> None:
        driver.get(self.login_url)
        self._fill(driver, "username", account.username)
        password_field = self._fill(driver, "password", account.password)
        try:
            self._click(driver, "login_submit")
        except Exception:
            password_field.send_keys("\n")
        self._wait_for_post_login(driver)

    def _open_domain(self, driver: Any, domain: str) -> bool:
        self._go_to_domains(driver)
        try:
            self._fill(driver, "domain_search", domain, clear_first=True)
        except OrangeAutomationNotConfigured:
            return False

        try:
            result = self._wait_for_any(driver, "domain_result", domain=domain)
        except OrangeAutomationNotConfigured:
            return False
        try:
            self._open_domain_nameservers(driver, result)
        except OrangeAutomationNotConfigured:
            return False
        self._wait_for_ready_state(driver)
        self._try_click(driver, "use_custom_nameservers")
        return True

    def _save_nameservers(self, driver: Any, nameservers: list[str]) -> None:
        if not self._submit_nameserver_form_via_script(driver, nameservers):
            self._fill(driver, "nameserver_1", nameservers[0], clear_first=True)
            self._fill(driver, "nameserver_2", nameservers[1], clear_first=True)
            self._clear_if_present(driver, "nameserver_3")
            self._clear_if_present(driver, "nameserver_4")
            self._clear_if_present(driver, "nameserver_5")
            self._finalize_form_inputs(driver)
            self._submit_nameserver_form(driver)
        self._wait_for_ready_state(driver)

    def _fill(self, driver: Any, key: str, value: str, clear_first: bool = True) -> Any:
        element = self._wait_for_any(driver, key)
        if clear_first:
            try:
                element.clear()
            except Exception:
                pass
        element.send_keys(value)
        self._dispatch_input_events(driver, element)
        return element

    def _clear_if_present(self, driver: Any, key: str) -> None:
        try:
            element = self._wait_for_any(driver, key, timeout=2)
        except OrangeAutomationNotConfigured:
            return
        try:
            element.clear()
        except Exception:
            pass
        self._dispatch_input_events(driver, element)

    def _finalize_form_inputs(self, driver: Any) -> None:
        try:
            self._try_click(driver, "use_custom_nameservers")
        except Exception:
            pass
        try:
            driver.execute_script("document.activeElement && document.activeElement.blur && document.activeElement.blur();")
        except Exception:
            pass
        try:
            body = driver.find_element("tag name", "body")
            body.click()
        except Exception:
            pass
        try:
            driver.execute_script(
                """
                const fields = Array.from(document.querySelectorAll("input"));
                fields.forEach((field) => {
                  field.dispatchEvent(new Event("change", { bubbles: true }));
                  field.dispatchEvent(new Event("blur", { bubbles: true }));
                });
                """
            )
        except Exception:
            pass

    def _click(self, driver: Any, key: str, **format_args: str) -> None:
        try:
            element = self._wait_for_clickable(driver, key, **format_args)
        except OrangeAutomationNotConfigured:
            element = self._wait_for_any(driver, key, **format_args)
        self._click_element(driver, element)

    def _click_element(self, driver: Any, element: Any) -> None:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        except Exception:
            pass
        try:
            element.click()
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", element)
            except Exception as exc:
                raise OrangeAutomationNotConfigured("Could not click the Orange page element.") from exc

    @staticmethod
    def _dispatch_input_events(driver: Any, element: Any) -> None:
        try:
            driver.execute_script(
                """
                const field = arguments[0];
                field.dispatchEvent(new Event("input", { bubbles: true }));
                field.dispatchEvent(new Event("change", { bubbles: true }));
                field.dispatchEvent(new Event("blur", { bubbles: true }));
                """,
                element,
            )
        except Exception:
            pass

    def _try_click(self, driver: Any, key: str, **format_args: str) -> bool:
        try:
            self._click(driver, key, **format_args)
            return True
        except OrangeAutomationNotConfigured:
            return False

    def _open_domain_nameservers(self, driver: Any, row: Any) -> None:
        toggle = self._find_within(row, "domain_actions_toggle")
        self._click_element(driver, toggle)
        self._click(driver, "manage_nameservers")

    def _find_within(self, root: Any, key: str, **format_args: str) -> Any:
        try:
            from selenium.webdriver.common.by import By
        except ImportError as exc:
            raise OrangeAutomationNotConfigured("Install Selenium first: pip install selenium") from exc

        by_map = {
            "css selector": By.CSS_SELECTOR,
            "xpath": By.XPATH,
        }

        last_error: Exception | None = None
        for strategy, raw_locator in self.SELECTORS[key]:
            locator = raw_locator.format(**format_args)
            try:
                return root.find_element(by_map[strategy], locator)
            except Exception as exc:
                last_error = exc
                continue
        raise OrangeAutomationNotConfigured(f"Could not find Orange selector group '{key}' inside the current domain row.") from last_error

    def _wait_for_any(self, driver: Any, key: str, timeout: int = 12, **format_args: str) -> Any:
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
        except ImportError as exc:
            raise OrangeAutomationNotConfigured("Install Selenium first: pip install selenium") from exc

        by_map = {
            "css selector": By.CSS_SELECTOR,
            "xpath": By.XPATH,
        }

        last_error: Exception | None = None
        for strategy, raw_locator in self.SELECTORS[key]:
            locator = raw_locator.format(**format_args)
            try:
                return WebDriverWait(driver, timeout).until(
                    lambda current_driver, search_by=by_map[strategy], search_value=locator: current_driver.find_element(search_by, search_value)
                )
            except Exception as exc:
                last_error = exc
                continue
        raise OrangeAutomationNotConfigured(f"Could not find Orange selector group '{key}'.") from last_error

    def _wait_for_clickable(self, driver: Any, key: str, timeout: int = 12, **format_args: str) -> Any:
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.support.ui import WebDriverWait
        except ImportError as exc:
            raise OrangeAutomationNotConfigured("Install Selenium first: pip install selenium") from exc

        by_map = {
            "css selector": By.CSS_SELECTOR,
            "xpath": By.XPATH,
        }

        last_error: Exception | None = None
        for strategy, raw_locator in self.SELECTORS[key]:
            locator = raw_locator.format(**format_args)
            try:
                return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by_map[strategy], locator)))
            except Exception as exc:
                last_error = exc
                continue
        raise OrangeAutomationNotConfigured(f"Could not find clickable Orange selector group '{key}'.") from last_error

    def _submit_nameserver_form(self, driver: Any) -> None:
        button = self._wait_for_any(driver, "save_nameservers")
        if self._attempt_submit(driver, button, mode="click"):
            return
        if self._attempt_submit(driver, button, mode="js_click"):
            return
        if self._attempt_submit(driver, button, mode="form_submit"):
            return
        raise OrangeAutomationNotConfigured("Could not submit the Orange nameserver form.")

    def _submit_nameserver_form_via_script(self, driver: Any, nameservers: list[str]) -> bool:
        previous_url = str(getattr(driver, "current_url", "") or "")
        try:
            submitted = bool(
                driver.execute_script(
                    """
                    const values = arguments[0];

                    const normalize = (text) => (text || "").replace(/\\s+/g, " ").trim().toLowerCase();
                    const labelInput = (labelText) => {
                      const labels = Array.from(document.querySelectorAll("label"));
                      const label = labels.find((item) => normalize(item.textContent).includes(labelText));
                      if (!label) return null;
                      let probe = label.nextElementSibling;
                      while (probe) {
                        const nestedInput = probe.matches && probe.matches("input") ? probe : probe.querySelector ? probe.querySelector("input") : null;
                        if (nestedInput) return nestedInput;
                        probe = probe.nextElementSibling;
                      }
                      return null;
                    };
                    const setField = (field, value) => {
                      if (!field) return;
                      field.focus();
                      field.value = value;
                      field.dispatchEvent(new Event("input", { bubbles: true }));
                      field.dispatchEvent(new Event("change", { bubbles: true }));
                      field.dispatchEvent(new Event("blur", { bubbles: true }));
                    };

                    const customRadio = document.querySelector("input[type='radio'][value='custom']")
                      || Array.from(document.querySelectorAll("label")).find((item) => normalize(item.textContent).includes("use custom nameservers"));
                    if (customRadio) {
                      if (customRadio.click) customRadio.click();
                      if ("checked" in customRadio) customRadio.checked = true;
                    }

                    const ns1 = document.querySelector("input[name='ns1'], input[name='nameserver1'], input[name='nameserver_1']") || labelInput("nameserver 1");
                    const ns2 = document.querySelector("input[name='ns2'], input[name='nameserver2'], input[name='nameserver_2']") || labelInput("nameserver 2");
                    const ns3 = document.querySelector("input[name='ns3'], input[name='nameserver3'], input[name='nameserver_3']") || labelInput("nameserver 3");
                    const ns4 = document.querySelector("input[name='ns4'], input[name='nameserver4'], input[name='nameserver_4']") || labelInput("nameserver 4");
                    const ns5 = document.querySelector("input[name='ns5'], input[name='nameserver5'], input[name='nameserver_5']") || labelInput("nameserver 5");

                    if (!ns1 || !ns2) return false;

                    setField(ns1, values[0] || "");
                    setField(ns2, values[1] || "");
                    setField(ns3, "");
                    setField(ns4, "");
                    setField(ns5, "");

                    const button = Array.from(document.querySelectorAll("button, input[type='submit']")).find((item) => {
                      const text = normalize(item.textContent || item.value || "");
                      return text === "change nameservers" || text.includes("change nameservers");
                    });
                    if (!button) return false;

                    const form = button.form || (button.closest ? button.closest("form") : null);
                    if (button.click) button.click();
                    if (form && form.requestSubmit) {
                      form.requestSubmit(button.tagName === "BUTTON" ? button : undefined);
                    } else if (form) {
                      form.submit();
                    }
                    return true;
                    """,
                    nameservers,
                )
            )
        except Exception:
            return False
        if not submitted:
            return False
        return self._wait_for_submit_confirmation(driver, None, previous_url)

    def _attempt_submit(self, driver: Any, button: Any, mode: str) -> bool:
        previous_url = str(getattr(driver, "current_url", "") or "")
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
        except Exception:
            pass

        try:
            if mode == "click":
                button.click()
            elif mode == "js_click":
                driver.execute_script("arguments[0].click();", button)
            elif mode == "form_submit":
                driver.execute_script(
                    "var btn = arguments[0]; var form = btn.form || btn.closest('form'); if (form) { form.submit(); }",
                    button,
                )
            else:
                return False
        except Exception:
            return False
        return self._wait_for_submit_confirmation(driver, button, previous_url)

    def _wait_for_submit_confirmation(self, driver: Any, button: Any, previous_url: str, timeout: int = 8) -> bool:
        try:
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.support.ui import WebDriverWait
        except ImportError as exc:
            raise OrangeAutomationNotConfigured("Install Selenium first: pip install selenium") from exc

        def submitted(current_driver: Any) -> bool:
            current_url = str(getattr(current_driver, "current_url", "") or "")
            if current_url != previous_url:
                return True
            if button is not None:
                try:
                    if EC.staleness_of(button)(current_driver):
                        return True
                except Exception:
                    return True
            try:
                self._wait_for_any(current_driver, "nameserver_submit_success", timeout=1)
                return True
            except OrangeAutomationNotConfigured:
                return False

        try:
            WebDriverWait(driver, timeout).until(submitted)
            return True
        except Exception:
            return False

    def _wait_for_post_login(self, driver: Any, timeout: int = 10) -> None:
        try:
            from selenium.webdriver.support.ui import WebDriverWait
        except ImportError as exc:
            raise OrangeAutomationNotConfigured("Install Selenium first: pip install selenium") from exc

        def logged_in(current_driver: Any) -> bool:
            current_url = str(getattr(current_driver, "current_url", "") or "")
            if "clientarea.php" in current_url:
                return True
            try:
                self._wait_for_any(current_driver, "post_login_marker", timeout=1)
                return True
            except OrangeAutomationNotConfigured:
                return False

        WebDriverWait(driver, timeout).until(logged_in)

    @staticmethod
    def _wait_for_ready_state(driver: Any, timeout: int = 12) -> None:
        try:
            from selenium.webdriver.support.ui import WebDriverWait
        except ImportError as exc:
            raise OrangeAutomationNotConfigured("Install Selenium first: pip install selenium") from exc

        WebDriverWait(driver, timeout).until(lambda current_driver: current_driver.execute_script("return document.readyState") == "complete")

    def _go_to_domains(self, driver: Any) -> None:
        current_url = str(getattr(driver, "current_url", "") or "")
        if self.DOMAINS_PATH in current_url:
            return
        parsed = urlsplit(self.login_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        domains_url = f"{base_url}{self.DOMAINS_PATH}"
        driver.get(domains_url)
        self._wait_for_ready_state(driver)

    @staticmethod
    def _is_connection_reset_error(exc: Exception) -> bool:
        current: Exception | None = exc
        seen: set[int] = set()
        while current is not None and id(current) not in seen:
            seen.add(id(current))
            text = str(current).lower()
            if "net::err_connection_reset" in text or "err_connection_reset" in text or "connection reset" in text:
                return True
            current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
        return False
