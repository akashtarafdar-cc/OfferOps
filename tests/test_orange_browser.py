import unittest
from unittest.mock import ANY, patch

from offerops.providers.orange_browser import OrangeAccount, OrangeAutomationNotConfigured, OrangeBrowserClient


class OrangeBrowserTests(unittest.TestCase):
    def test_dry_run_reports_configured_accounts_and_nameservers(self) -> None:
        client = OrangeBrowserClient(
            login_url="https://secure.orangewebsite.com/login",
            accounts=[
                OrangeAccount("sweeps_live", "user1", "pass1"),
                OrangeAccount("sweeps_bkp", "", ""),
                OrangeAccount("ecom_live", "user2", "pass2"),
            ],
            dry_run=True,
        )

        result = client.update_nameservers("example.com", ["ns1.example.com", "ns2.example.com"])

        self.assertEqual(result["matched_account"], "dry-run")
        self.assertEqual(result["searched_accounts"], ["sweeps_live", "ecom_live"])
        self.assertEqual(result["nameservers"], ["ns1.example.com", "ns2.example.com"])

    def test_requires_two_nameservers(self) -> None:
        client = OrangeBrowserClient(
            login_url="https://secure.orangewebsite.com/login",
            accounts=[OrangeAccount("sweeps_live", "user1", "pass1")],
            dry_run=False,
        )

        with self.assertRaisesRegex(Exception, "At least two nameservers are required"):
            client.update_nameservers("example.com", ["ns1.example.com"])

    def test_click_falls_back_to_javascript(self) -> None:
        client = OrangeBrowserClient(
            login_url="https://secure.orangewebsite.com/login",
            accounts=[],
            dry_run=False,
        )

        class FakeElement:
            def click(self) -> None:
                raise Exception("not interactable")

        class FakeDriver:
            def __init__(self) -> None:
                self.scripts: list[str] = []

            def execute_script(self, script: str, element: object) -> None:
                self.scripts.append(script)

        driver = FakeDriver()

        with patch.object(client, "_wait_for_clickable", return_value=FakeElement()):
            client._click(driver, "login_submit")

        self.assertIn("arguments[0].click();", driver.scripts)

    def test_go_to_domains_uses_clientarea_domains_url(self) -> None:
        client = OrangeBrowserClient(
            login_url="https://secure.orangewebsite.com/login",
            accounts=[],
            dry_run=False,
        )

        class FakeDriver:
            def __init__(self) -> None:
                self.current_url = "https://secure.orangewebsite.com/clientarea.php"
                self.visited: list[str] = []

            def get(self, url: str) -> None:
                self.visited.append(url)
                self.current_url = url

        driver = FakeDriver()

        with patch.object(client, "_wait_for_ready_state", return_value=None):
            client._go_to_domains(driver)

        self.assertEqual(driver.visited, ["https://secure.orangewebsite.com/clientarea.php?action=domains"])

    def test_open_domain_nameservers_uses_row_dropdown(self) -> None:
        client = OrangeBrowserClient(
            login_url="https://secure.orangewebsite.com/login",
            accounts=[],
            dry_run=False,
        )

        class FakeRow:
            pass

        row = FakeRow()
        toggle = object()

        with patch.object(client, "_find_within", return_value=toggle) as find_mock:
            with patch.object(client, "_click_element") as click_element_mock:
                with patch.object(client, "_click") as click_mock:
                    client._open_domain_nameservers(object(), row)

        find_mock.assert_called_once_with(row, "domain_actions_toggle")
        click_element_mock.assert_called_once_with(ANY, toggle)
        click_mock.assert_called_once_with(ANY, "manage_nameservers")

    def test_click_falls_back_to_visible_element_when_clickable_wait_fails(self) -> None:
        client = OrangeBrowserClient(
            login_url="https://secure.orangewebsite.com/login",
            accounts=[],
            dry_run=False,
        )
        element = object()

        with patch.object(client, "_wait_for_clickable", side_effect=OrangeAutomationNotConfigured("timeout")):
            with patch.object(client, "_wait_for_any", return_value=element) as wait_any_mock:
                with patch.object(client, "_click_element") as click_element_mock:
                    client._click(object(), "save_nameservers")

        wait_any_mock.assert_called_once_with(ANY, "save_nameservers")
        click_element_mock.assert_called_once_with(ANY, element)

    def test_wait_for_post_login_accepts_clientarea_url(self) -> None:
        client = OrangeBrowserClient(
            login_url="https://secure.orangewebsite.com/login",
            accounts=[],
            dry_run=False,
        )

        class FakeDriver:
            current_url = "https://secure.orangewebsite.com/clientarea.php"

        client._wait_for_post_login(FakeDriver())

    def test_submit_nameserver_form_uses_form_submit_fallback(self) -> None:
        client = OrangeBrowserClient(
            login_url="https://secure.orangewebsite.com/login",
            accounts=[],
            dry_run=False,
        )
        button = object()

        with patch.object(client, "_wait_for_any", return_value=button):
            with patch.object(client, "_attempt_submit", side_effect=[False, False, True]) as submit_mock:
                client._submit_nameserver_form(object())

        self.assertEqual(
            [call.kwargs["mode"] for call in submit_mock.call_args_list],
            ["click", "js_click", "form_submit"],
        )

    def test_submit_nameserver_form_via_script_waits_for_confirmation(self) -> None:
        client = OrangeBrowserClient(
            login_url="https://secure.orangewebsite.com/login",
            accounts=[],
            dry_run=False,
        )

        class FakeDriver:
            current_url = "https://secure.orangewebsite.com/clientarea.php?action=domaindetails&id=1#tabNameservers"

            def execute_script(self, script: str, nameservers: list[str]) -> bool:
                return True

        driver = FakeDriver()

        with patch.object(client, "_wait_for_submit_confirmation", return_value=True) as confirm_mock:
            result = client._submit_nameserver_form_via_script(driver, ["ns1.example.com", "ns2.example.com"])

        self.assertTrue(result)
        confirm_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
