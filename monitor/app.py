"""Minimal monitor: serves /api/health (fly.toml) and a dashboard page
reading state/ticks.jsonl. stdlib only.
"""
import json
import pathlib
from http.server import BaseHTTPRequestHandler, HTTPServer

STATE = pathlib.Path("state/ticks.jsonl")

PAGE = """<!doctype html><html><head><title>slingshot monitor</title>
<style>body{background:#0a0a0a;color:#e4e4e7;font-family:monospace;padding:2rem}
.card{border:1px solid #27272a;border-radius:12px;padding:1rem;margin-bottom:1rem;max-width:600px}
.big{font-size:2rem;font-weight:bold}.green{color:#4ade80}.red{color:#f87171}
button{background:#dc2626;color:#fff;border:none;border-radius:8px;padding:.6rem 1.2rem;font-weight:bold;cursor:pointer}
</style></head><body>
<h1>🪂 slingshot monitor <small style="color:#71717a">paper</small></h1>
<div class="card"><div>BANKROLL</div><div class="big" id="bank">…</div>
<div>realized PnL: <span id="pnl">…</span> · open: <span id="open">…</span> · fills: <span id="fills">…</span> · dd: <span id="dd">…</span></div></div>
<div class="card"><div>LAST DECISION</div><pre id="dec">…</pre></div>
<div class="card"><button onclick="if(confirm('Flatten everything?'))fetch('/api/kill',{method:'POST'}).then(()=>alert('kill file written'))">
KILL SWITCH — flatten all</button></div>
<script>
async function refresh(){
  const r = await fetch('/api/status').then(r=>r.json());
  bank.textContent = '$'+r.ledger.bankroll.toFixed(2);
  pnl.textContent = '$'+r.ledger.realized_pnl.toFixed(2);
  open.textContent = r.ledger.open_positions;
  fills.textContent = r.ledger.fills;
  dd.textContent = r.ledger.drawdown_pct+'%';
  dec.textContent = JSON.stringify(r.decision,null,1);
}
refresh(); setInterval(refresh,5000);
</script></body></html>
"""


def last_tick():
    if not STATE.exists():
        return None
    lines = STATE.read_text().strip().split("\n")
    return json.loads(lines[-1]) if lines and lines[0] else None


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/health":
            self._send(200, json.dumps({"ok": True, "mode": "paper"}))
        elif self.path == "/api/status":
            t = last_tick()
            self._send(200, json.dumps(t or {"ledger": {}, "decision": {}}))
        elif self.path in ("/", "/dashboard"):
            self._send(200, PAGE, "text/html")
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path == "/api/kill":
            pathlib.Path("/tmp/slingshot_kill").write_text("manual")
            self._send(200, json.dumps({"killed": True}))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def log_message(self, *a):
        pass


def serve(port=3000):
    print(f"monitor on http://localhost:{port}  (/api/health for fly)")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    serve()
