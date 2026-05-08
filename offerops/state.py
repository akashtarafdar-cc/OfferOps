from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import JobResult, StepResult, StepStatus


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"jobs": {}}
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def write(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
        tmp.replace(self.path)

    def save_result(self, result: JobResult) -> None:
        data = self.read()
        data.setdefault("jobs", {})[result.domain] = {
            "domain": result.domain,
            "profile": result.profile,
            "status": result.status.value,
            "steps": [
                {"name": step.name, "status": step.status.value, "message": step.message, "data": step.data}
                for step in result.steps
            ],
        }
        self.write(data)

    def save_credentials(self, domain: str, data: dict[str, Any]) -> Path:
        credentials_dir = self.path.parent / "credentials"
        credentials_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in domain)
        output_path = credentials_dir / f"{safe_name}.json"
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
        return output_path

    def completed(self, domain: str, step_name: str) -> bool:
        job = self.read().get("jobs", {}).get(domain, {})
        return any(step.get("name") == step_name and step.get("status") == StepStatus.DONE for step in job.get("steps", []))


def step_from_exception(name: str, exc: Exception) -> StepResult:
    return StepResult(name=name, status=StepStatus.FAILED, message=str(exc))
