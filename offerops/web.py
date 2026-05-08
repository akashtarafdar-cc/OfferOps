from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .config import AppConfig, Settings
from .state import StateStore


INDEX = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OfferOps</title>
  <style>
    :root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, Segoe UI, Arial, sans-serif; }
    body { margin: 0; background: #f7f4ee; color: #18212f; }
    header { padding: 28px 32px 16px; background: #17202f; color: white; }
    h1 { margin: 0 0 6px; font-size: 32px; font-weight: 750; letter-spacing: 0; }
    header p { margin: 0; color: #d6e4ef; max-width: 820px; }
    main { padding: 24px 32px 40px; max-width: 1120px; margin: 0 auto; }
    .bar { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-bottom: 18px; }
    button { appearance: none; border: 0; background: #0e7c66; color: white; border-radius: 6px; padding: 10px 14px; font-weight: 700; cursor: pointer; }
    table { width: 100%; border-collapse: collapse; background: white; border: 1px solid #ded8cb; }
    th, td { padding: 12px 14px; text-align: left; border-bottom: 1px solid #ebe6dc; vertical-align: top; }
    th { font-size: 13px; text-transform: uppercase; color: #5a6573; background: #fbfaf7; }
    .status { display: inline-flex; min-width: 72px; justify-content: center; border-radius: 999px; padding: 4px 8px; font-size: 12px; font-weight: 800; }
    .done { background: #d9f5e8; color: #0b684e; }
    .failed { background: #ffe0dc; color: #9b241a; }
    .pending, .skipped { background: #edf0f4; color: #465466; }
    code { white-space: pre-wrap; overflow-wrap: anywhere; }
    @media (max-width: 720px) {
      main, header { padding-left: 16px; padding-right: 16px; }
      table, thead, tbody, tr, th, td { display: block; }
      thead { display: none; }
      tr { border-bottom: 1px solid #ded8cb; }
    }
  </style>
</head>
<body>
  <header>
    <h1>OfferOps</h1>
    <p>Domain, Cloudflare, cPanel, mail deliverability, file, database, and cron provisioning tracker.</p>
  </header>
  <main>
    <div class="bar">
      <strong id="count">Loading jobs...</strong>
      <button onclick="load()">Refresh</button>
    </div>
    <table>
      <thead><tr><th>Domain</th><th>Profile</th><th>Status</th><th>Steps</th></tr></thead>
      <tbody id="jobs"></tbody>
    </table>
  </main>
  <script>
    async function load() {
      const response = await fetch('/api/state');
      const data = await response.json();
      const jobs = Object.values(data.jobs || {});
      document.getElementById('count').textContent = `${jobs.length} saved job${jobs.length === 1 ? '' : 's'}`;
      document.getElementById('jobs').innerHTML = jobs.map(job => `
        <tr>
          <td><strong>${escapeHtml(job.domain)}</strong></td>
          <td>${escapeHtml(job.profile)}</td>
          <td><span class="status ${escapeHtml(job.status)}">${escapeHtml(job.status)}</span></td>
          <td>${(job.steps || []).map(step => `<div><span class="status ${escapeHtml(step.status)}">${escapeHtml(step.status)}</span> ${escapeHtml(step.name)} <code>${escapeHtml(step.message || '')}</code></div>`).join('')}</td>
        </tr>
      `).join('');
    }
    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
    }
    load();
  </script>
</body>
</html>"""


def serve(host: str, port: int, settings: Settings, config: AppConfig, state: StateStore) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/" or self.path.startswith("/index.html"):
                self._send(200, INDEX, "text/html; charset=utf-8")
                return
            if self.path.startswith("/api/state"):
                self._send_json(200, state.read())
                return
            if self.path.startswith("/api/config"):
                payload = {"config_path": str(settings.config_path), "state_path": str(settings.state_path), "profiles": list(config.raw.get("profiles", {}).keys())}
                self._send_json(200, payload)
                return
            self._send_json(404, {"error": "not found"})

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

        def _send(self, status: int, payload: str | bytes, content_type: str) -> None:
            body = payload.encode("utf-8") if isinstance(payload, str) else payload
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    print(f"OfferOps dashboard: http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()

