#!/usr/bin/env python3
"""serve.py -- http://localhost:8099/dashboard.html con proxy CORS para Supadata
Sirve dashboard.html estático y hace proxy de /v1/* -> https://pro-serv.tail9f39ff.ts.net/v1/*
para que el fetch del browser no haga preflight CORS. Mantiene CORS headers.
Uso: python scripts/serve.py  (puerto 8099)
"""
import http.server, socketserver, urllib.request, urllib.error, os, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
SUPA = "https://pro-serv.tail9f39ff.ts.net"
PORT = 3000

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,x-api-key,X-Client-Name,Authorization")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        super().end_headers()
    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.path = "/dashboard.html"
        if self.path.startswith("/v1/") or self.path.startswith("/health"):
            self.proxy()
        else:
            super().do_GET()
    def do_POST(self):
        if self.path.startswith("/v1/"):
            self.proxy()
        else:
            self.send_error(404)
    def do_PUT(self):
        if self.path.startswith("/v1/"):
            self.proxy()
        else:
            self.send_error(404)
    def do_DELETE(self):
        if self.path.startswith("/v1/"):
            self.proxy()
        else:
            self.send_error(404)
    def proxy(self):
        url = SUPA + self.path
        data = None
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            data = self.rfile.read(length)
        headers = {}
        for k in ("x-api-key","X-Api-Key","Content-Type","X-Client-Name","Authorization"):
            v = self.headers.get(k) or self.headers.get(k.lower())
            if v:
                headers[k] = v
        headers["X-Client-Name"] = self.headers.get("X-Client-Name") or "panel-control-proxy"
        # si el browser no mandó key (JS ya no hardcodea), inyecta desde env/mcp local
        if "x-api-key" not in headers and "X-Api-Key" not in headers and "Authorization" not in headers:
            _k = (os.environ.get("SUPADATA_API_KEY") or "").strip()
            if not _k:
                try:
                    import json as _js
                    for _p in [os.path.expanduser(r"~\.config\opencode\opencode.json"), str(ROOT / ".opencode" / "opencode.json")]:
                        if os.path.exists(_p):
                            _c = _js.load(open(_p, encoding="utf-8-sig"))
                            _k = (((_c.get("mcp", {}) or {}).get("supadata", {}).get("environment", {}) or {}).get("SUPADATA_API_KEY", "") or "").strip()
                            if _k: break
                except: pass
            if _k:
                if _k.startswith("eyJ"):
                    headers["Authorization"] = f"Bearer {_k}"
                else:
                    headers["x-api-key"] = _k
        # forward
        req = urllib.request.Request(url, data=data, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                self.send_response(r.status)
                ctype = r.headers.get("Content-Type","application/json")
                self.send_header("Content-Type", ctype)
                self.end_headers()
                self.wfile.write(r.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(f'{{"error":"proxy {e}"}}'.encode())

if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving {ROOT} + proxy Supadata at http://localhost:{PORT}/dashboard.html")
        print(f"Proxy: http://localhost:{PORT}/v1/* -> {SUPA}/v1/*")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
