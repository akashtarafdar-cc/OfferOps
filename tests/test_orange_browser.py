import unittest

from offerops.providers.orange_browser import OrangeAccount, OrangeBrowserClient


class OrangeBrowserTests(unittest.TestCase):
    def test_dry_run_reports_configured_accounts_and_nameservers(self) -> None:
        client = OrangeBrowserClient(
            login_url="https://orange.example.com/login",
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


if __name__ == "__main__":
    unittest.main()

