from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ..http import JsonHttpClient
from ..models import DnsRecord


class CloudflareClient:
    def __init__(self, api_token: str, account_id: str, dry_run: bool = False) -> None:
        self.account_id = account_id
        self.dry_run = dry_run
        self.http = JsonHttpClient(
            "https://api.cloudflare.com/client/v4",
            headers={"Authorization": f"Bearer {api_token}"} if api_token else {},
        )

    def ensure_zone(self, domain: str, plan: str = "free") -> dict[str, Any]:
        if self.dry_run:
            return {"id": f"dry-zone-{domain}", "name_servers": ["dry.ns.cloudflare.com", "dry2.ns.cloudflare.com"]}
        existing = self.http.request("GET", "/zones", query={"name": domain}).body
        results = existing.get("result", []) if isinstance(existing, dict) else []
        if results:
            zone = results[0]
            return {"id": zone["id"], "name_servers": zone.get("name_servers", [])}
        payload = {"name": domain, "account": {"id": self.account_id}, "jump_start": False, "type": "full"}
        created = self.http.request("POST", "/zones", json_body=payload).body
        result = created["result"]
        return {"id": result["id"], "name_servers": result.get("name_servers", []), "plan": plan}

    def set_bot_fight_mode(self, zone_id: str, enabled: bool = True) -> dict[str, Any]:
        if self.dry_run:
            return {"id": "bot_fight_mode", "value": "on" if enabled else "off", "editable": True}
        payload = {"value": "on" if enabled else "off"}
        response = self.http.request("PATCH", f"/zones/{zone_id}/settings/bot_fight_mode", json_body=payload).body
        return response["result"]

    def upsert_dns_record(self, zone_id: str, record: DnsRecord, domain: str) -> dict[str, Any]:
        if self.dry_run:
            return {"id": f"dry-dns-{record.type}-{record.name}", **asdict(record)}
        normalized_name = self._normalize_name(record.name, domain)
        query = {"type": record.type, "name": normalized_name}
        existing = self.http.request("GET", f"/zones/{zone_id}/dns_records", query=query).body
        payload = {"type": record.type, "name": normalized_name, "content": record.content, "ttl": record.ttl}
        if record.type in {"A", "AAAA", "CNAME"}:
            payload["proxied"] = record.proxied
        if record.priority is not None:
            payload["priority"] = record.priority
        results = existing.get("result", []) if isinstance(existing, dict) else []
        if results:
            record_id = results[0]["id"]
            return self.http.request("PUT", f"/zones/{zone_id}/dns_records/{record_id}", json_body=payload).body["result"]
        return self.http.request("POST", f"/zones/{zone_id}/dns_records", json_body=payload).body["result"]

    @staticmethod
    def _normalize_name(name: str, domain: str) -> str:
        stripped = name.strip()
        if stripped == "@":
            return domain
        if stripped.endswith(f".{domain}") or stripped == domain:
            return stripped
        return f"{stripped}.{domain}"
