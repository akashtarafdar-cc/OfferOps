from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from urllib.parse import urlparse


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class DnsRecord:
    type: str
    name: str
    content: str
    ttl: int = 1
    proxied: bool = False
    priority: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], domain: str, ttl: int) -> "DnsRecord":
        return cls(
            type=str(data["type"]).upper(),
            name=str(data["name"]).format(domain=domain),
            content=str(data["content"]).format(domain=domain),
            ttl=int(data.get("ttl", ttl)),
            proxied=bool(data.get("proxied", False)),
            priority=int(data["priority"]) if "priority" in data else None,
        )


@dataclass(frozen=True)
class CronSpec:
    minute: str
    hour: str
    day: str
    month: str
    weekday: str
    command: str


@dataclass(frozen=True)
class DomainJob:
    domain: str
    profile: str
    offer_path: str = ""
    notes: str = ""

    def resolved_offer_path(self) -> str:
        raw = self.offer_path.strip()
        if not raw:
            return ""
        parsed = urlparse(raw)
        path = parsed.path if parsed.scheme and parsed.netloc else raw
        return path.strip("/")


@dataclass
class StepResult:
    name: str
    status: StepStatus
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class JobResult:
    domain: str
    profile: str
    status: StepStatus
    steps: list[StepResult] = field(default_factory=list)

    def add(self, result: StepResult) -> None:
        self.steps.append(result)
        if result.status == StepStatus.FAILED:
            self.status = StepStatus.FAILED
