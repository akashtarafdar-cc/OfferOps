from __future__ import annotations

import csv
from pathlib import Path

from .models import DomainJob


def load_jobs(path: Path) -> list[DomainJob]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"domain", "profile"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV missing required columns: {', '.join(sorted(missing))}")
        jobs: list[DomainJob] = []
        for row in reader:
            domain = (row.get("domain") or "").strip().lower()
            profile = (row.get("profile") or "").strip()
            offer_path = (row.get("offer_path") or row.get("offer_url") or row.get("offer") or "").strip()
            if not domain or domain.startswith("#"):
                continue
            jobs.append(DomainJob(domain, profile, offer_path, (row.get("notes") or "").strip()))
        return jobs
