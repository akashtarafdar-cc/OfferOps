from pathlib import Path
import unittest

from offerops.importer import load_jobs


class ImporterTests(unittest.TestCase):
    def test_load_jobs_from_csv(self) -> None:
        csv_text = (
            "domain,profile,offer_path,notes\n"
            "example-offer.com,ecom-live,https://www.example-offer.com/v1/msrack,\n"
            "example-sweeps.com,sweeps-live,https://www.example-sweeps.com/v1/msrack,\n"
        )
        path = self._write_csv(csv_text)
        jobs = load_jobs(path)
        self.assertEqual([job.domain for job in jobs], ["example-offer.com", "example-sweeps.com"])
        self.assertEqual(jobs[0].profile, "ecom-live")
        self.assertEqual(jobs[0].resolved_offer_path(), "v1/msrack")
        self.assertEqual(jobs[1].profile, "sweeps-live")

    def test_offer_path_can_be_full_url(self) -> None:
        csv_text = "domain,profile,offer_path,notes\nexample.com,sweeps-live,https://www.example.com/v1/msrack,\n"
        path = self._write_csv(csv_text)
        jobs = load_jobs(path)
        self.assertEqual(jobs[0].resolved_offer_path(), "v1/msrack")

    def _write_csv(self, content: str) -> Path:
        base = Path(".tmp") / "test-importer"
        base.mkdir(parents=True, exist_ok=True)
        path = base / f"{self.id().split('.')[-1]}.csv"
        path.write_text(content, encoding="utf-8")
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path


if __name__ == "__main__":
    unittest.main()
