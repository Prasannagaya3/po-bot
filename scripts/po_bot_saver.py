"""
PO Bot Local Saver — http://localhost:9847
Accepts project files from the browser and saves them locally.

Usage: python scripts/po_bot_saver.py
   or: double-click scripts/start_saver.bat
"""

import http.server, json, os, re, base64

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

        try:
            os.makedirs(project_dir, exist_ok=True)
            for f in files:
                fname     = safe_name(f.get("filename") or "file")
                content   = f.get("content") or ""
                encoding  = f.get("encoding") or ""
                subfolder = f.get("subfolder") or ""
                target = project_dir
                if subfolder:
                    target = os.path.join(project_dir, safe_name(subfolder))
                    os.makedirs(target, exist_ok=True)
                fpath = os.path.join(target, fname)
                if encoding == "base64":
                    with open(fpath, "wb") as fp:
                        fp.write(base64.b64decode(content))
                else:
                    with open(fpath, "w", encoding="utf-8") as fp:
                        fp.write(content)
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


MARKER_FILE = os.path.join(BASE_DIR, ".saver_installed")

def ensure_startup():
    if os.path.exists(MARKER_FILE):
        print("Already in startup.")
        return
    try:
        import winreg
        saver_path = os.path.join(os.path.dirname(__file__), "start_saver.pyw")
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "PO Bot Saver", 0, winreg.REG_SZ, f'pythonw "{saver_path}"')
        winreg.CloseKey(key)
        os.makedirs(BASE_DIR, exist_ok=True)
        open(MARKER_FILE, "w").close()
        print("PO Bot Saver added to Windows startup - will run automatically on login.")
    except Exception as e:
        print(f"Could not add to startup: {e}")


if __name__ == "__main__":
    server = http.server.HTTPServer(("localhost", PORT), Handler)
    print(f"PO Bot Saver running on http://localhost:{PORT}")
    print(f"Saving projects to: {BASE_DIR}")
    print("Press Ctrl+C to stop.")
    ensure_startup()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
