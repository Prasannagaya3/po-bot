"""
PO Bot Local Saver — http://localhost:9847
Accepts project files from the browser and saves them locally.

Usage: python scripts/po_bot_saver.py
   or: double-click scripts/start_saver.bat
"""

import http.server, json, os, re

BASE_DIR = r"D:\Work\Unity_Applications\Product Development"
PORT = 9847
ALLOWED_ORIGIN = "https://prasannagaya3.github.io"


def safe_name(s):
    return re.sub(r'[<>:"/\\|?*]', '_', s).strip(". ")


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress per-request logs

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", ALLOWED_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/ping":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors()
            self.end_headers()
            self.wfile.write(json.dumps({"running": True}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/save":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length))
        except Exception:
            self._err("Invalid JSON")
            return

        project_name = (data.get("project_name") or "").strip()
        files = data.get("files") or []

        if not project_name:
            self._err("Missing project_name")
            return

        project_dir = os.path.join(BASE_DIR, safe_name(project_name))
        orig_docs_dir = os.path.join(project_dir, "original_docs")

        try:
            os.makedirs(project_dir, exist_ok=True)
            os.makedirs(orig_docs_dir, exist_ok=True)
            for f in files:
                fname = safe_name(f.get("filename") or "file")
                with open(os.path.join(project_dir, fname), "w", encoding="utf-8") as fp:
                    fp.write(f.get("content") or "")
            print(f"  Saved: {project_dir}")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors()
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "path": project_dir}).encode())
        except Exception as e:
            self._err(str(e))

    def _err(self, msg):
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(json.dumps({"success": False, "error": msg}).encode())


if __name__ == "__main__":
    server = http.server.HTTPServer(("localhost", PORT), Handler)
    print(f"PO Bot Saver running on http://localhost:{PORT}")
    print(f"Saving projects to: {BASE_DIR}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
