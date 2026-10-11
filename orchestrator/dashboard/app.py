"""Local dashboard (stdlib only). Optional; CLI works without it.

All endpoints reflect LIVE state: health matrix, /v1/models discovery,
SQLite history, and the latest report.json.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse


class Handler(BaseHTTPRequestHandler):
    root: Path = Path(".")

    def log_message(self, *a):
        pass

    def _send(self, body: str, ctype: str = "text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj) -> str:
        return json.dumps(obj, indent=2, ensure_ascii=False)

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path == "/api/health":
                return self._send(self._json({"ok": True}), "application/json")
            if u.path == "/api/agents":
                from orchestrator.core.agent_matrix import AgentMatrix
                from orchestrator.core.config import get_config
                m = AgentMatrix(get_config(), ".").check_all()
                return self._send(self._json({k: {"status": v.status, "healthy": v.healthy,
                                                  "reason": v.reason, "action": v.action,
                                                  "local": v.local, "free": v.free} for k, v in m.items()}),
                                  "application/json")
            if u.path == "/api/models":
                from orchestrator.core.config import get_config
                from orchestrator.core.model_discovery import ModelDiscovery
                d = ModelDiscovery(get_config()).discover()
                return self._send(self._json(
                    {src: [{"id": m.id, "owned_by": m.owned_by,
                            "context_length": m.context_length, "coding": m.coding}
                           for m in models] for src, models in d.items()}), "application/json")
            if u.path == "/api/supervisor":
                from orchestrator.core.config import get_config
                cfg = get_config().config
                return self._send(self._json({
                    "task_modes": cfg.supervisor.task_modes,
                    "default_mode": cfg.supervisor.default_mode,
                    "cost_policy": cfg.supervisor.cost_policy,
                    "max_attempts": cfg.supervisor.max_attempts,
                    "free_only": cfg.general.free_only,
                    "local_first": cfg.general.local_first,
                    "secret_scanner": cfg.secret_scanner.enabled,
                    "pipeline": ["Analysis", "Discovery", "Plan", "Route", "Security",
                                 "Execute", "Validate", "Test", "Repair", "Review", "Report"],
                }), "application/json")
            if u.path == "/api/latest":
                rep = self._latest_report()
                return self._send(self._json(rep or {"status": "no runs yet"}), "application/json")
            if u.path == "/api/tasks":
                from orchestrator.core.config import get_config
                from orchestrator.core.database import get_database
                cfg = get_config()
                db = get_database(cfg.config.history.db_path)
                tasks = db.get_all_tasks(limit=30)
                out = [{"task_id": t.task_id, "date": t.date, "agent": t.selected_agent,
                        "result": t.result, "project": t.project_path,
                        "task": t.task_description[:120]} for t in tasks]
                return self._send(self._json(out), "application/json")
        except Exception as e:
            return self._send(self._json({"error": str(e)[:300]}), "application/json")
        self._send(self._page())

    def _latest_report(self):
        logs = self.root / "logs"
        if not logs.exists():
            return None
        cands = sorted(logs.glob("*/*/report.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not cands:
            return None
        try:
            rep = json.loads(cands[0].read_text(encoding="utf-8"))
            return {"task_id": rep.get("task_id"), "status": rep.get("status"),
                    "agent": rep.get("agent"), "model": rep.get("model"),
                    "execution_mode": rep.get("execution_mode"),
                    "attempts": rep.get("attempts"), "duration": rep.get("duration"),
                    "files_changed": rep.get("files_changed"),
                    "validation": rep.get("validation"),
                    "fallbacks": rep.get("fallbacks", []),
                    "warnings": rep.get("warnings", []),
                    "errors": [str(e)[:200] for e in (rep.get("errors") or [])][:5]}
        except Exception:
            return None

    def _page(self) -> str:
        return """<!doctype html><html><head><meta charset=utf-8><title>AI Coding Supervisor</title>
<style>body{background:#0b0b0c;color:#e8e8e8;font-family:Consolas,monospace;margin:0}
header{border-bottom:1px solid #c9a227;padding:16px 24px}h1{margin:0;font-size:18px;letter-spacing:2px}
h1 span{color:#c9a227}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:24px}
.card{background:#141416;border:1px solid #2a2a2e;border-radius:10px;padding:16px;min-width:0}
.card h2{margin:0 0 12px;font-size:13px;color:#c9a227;letter-spacing:1px}
pre{white-space:pre-wrap;font-size:12px;color:#cfcfcf}a{color:#c9a227}</style></head>
<body><header><h1>AI CODING <span>SUPERVISOR</span> — live</h1></header>
<div class=grid>
<div class=card><h2>SYSTEM + POLICY</h2><pre id=sup>loading...</pre></div>
<div class=card><h2>AGENTS (LIVE)</h2><pre id=agents>loading...</pre></div>
<div class=card><h2>MODELS (LIVE /v1/models)</h2><pre id=models>loading...</pre></div>
<div class=card><h2>CURRENT TASK (LATEST REPORT)</h2><pre id=latest>loading...</pre></div>
<div class=card><h2>PIPELINE</h2><pre>Analysis -> Discovery -> Plan -> Route -> Security -> Execute -> Validate -> Test -> Repair -> Review -> Report</pre></div>
<div class=card><h2>RECENT TASKS</h2><pre id=tasks>loading...</pre></div>
</div>
<script>
const set=(id,v)=>{document.getElementById(id).textContent=typeof v==='string'?v:JSON.stringify(v,null,2)};
fetch('/api/supervisor').then(r=>r.json()).then(set.bind(null,'sup'));
fetch('/api/agents').then(r=>r.json()).then(set.bind(null,'agents'));
fetch('/api/models').then(r=>r.json()).then(set.bind(null,'models'));
fetch('/api/latest').then(r=>r.json()).then(set.bind(null,'latest'));
fetch('/api/tasks').then(r=>r.json()).then(set.bind(null,'tasks'));
</script></body></html>"""


def serve(root: str | Path, host: str = "127.0.0.1", port: int = 8787):
    Handler.root = Path(root)
    httpd = HTTPServer((host, port), Handler)
    print(f"Dashboard: http://{host}:{port}  (Ctrl+C to stop)")
    httpd.serve_forever()
