#!/usr/bin/env python3
"""Exercise a standalone ThirtyFile binary using only the Python standard library."""

import argparse
import base64
import hashlib
from html.parser import HTMLParser
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


class Assets(HTMLParser):
    """Collect local scripts and styles referenced by the embedded HTML page."""

    def __init__(self):
        super().__init__()
        self.paths = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        path = attrs.get("src") if tag == "script" else attrs.get("href") if tag == "link" else None
        if path and path.startswith("/") and not path.startswith("/api/") and path.split("?")[0].endswith((".js", ".css")):
            self.paths.add(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    source = args.binary.resolve(strict=True)
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    report = {"binary_sha256": digest, "checks": [], "status": "running"}
    process = None

    def checked(condition, description):
        if not condition:
            raise AssertionError(description)
        report["checks"].append(description)
        print("PASS:", description, flush=True)

    def stop():
        nonlocal process
        if process is None:
            return
        if os.name == "nt":
            # A helper joins only the child's console, so Ctrl+C cannot reach the CI runner.
            helper = """import ctypes, sys
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.FreeConsole()
if not kernel.AttachConsole(int(sys.argv[1])):
    raise ctypes.WinError(ctypes.get_last_error())
if not kernel.SetConsoleCtrlHandler(None, True):
    raise ctypes.WinError(ctypes.get_last_error())
if not kernel.GenerateConsoleCtrlEvent(0, 0):
    raise ctypes.WinError(ctypes.get_last_error())
kernel.FreeConsole()
"""
            import sys
            subprocess.run([sys.executable, "-c", helper, str(process.pid)], check=True, timeout=10)
        else:
            process.send_signal(signal.SIGTERM)
        try:
            code = process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            process = None
            raise AssertionError("server did not stop within 20 seconds")
        process = None
        event = "Ctrl+C" if os.name == "nt" else "SIGTERM"
        checked(code == 0, f"server exits cleanly on {event}")

    try:
        with tempfile.TemporaryDirectory(prefix="thirtyfile 中文 single ") as temporary:
            root = Path(temporary)
            binary = root / ("thirtyfile.exe" if os.name == "nt" else "thirtyfile")
            shutil.copy2(source, binary)
            binary.chmod(0o755)
            checked(list(root.iterdir()) == [binary], "clean working directory initially contains only the executable")
            checked(hashlib.sha256(binary.read_bytes()).hexdigest() == digest, "tested executable matches the uploaded artifact")
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            address = f"127.0.0.1:{port}"
            base = f"http://{address}"
            credential = secrets.token_urlsafe(24)
            env = {key: value for key, value in os.environ.items() if not key.startswith("THIRTYFILE_")}
            env.update(THIRTYFILE_ADDR=address, THIRTYFILE_ADMIN_PASSWORD=credential, THIRTYFILE_LOG_FORMAT="json")
            cookies = http.cookiejar.CookieJar()
            client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))

            def request(path, method="GET", data=None, headers=None, authenticated=True):
                headers = dict(headers or {})
                if isinstance(data, dict):
                    headers["Content-Type"] = "application/json"
                    data = json.dumps(data).encode()
                req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
                opener = client if authenticated else urllib.request.build_opener()
                with opener.open(req, timeout=10) as response:
                    return response.status, response.headers, response.read()

            def json_request(path, method="GET", data=None):
                return json.loads(request(path, method, data)[2])

            def expect_status(path, expected, method="GET", data=None, authenticated=True):
                try:
                    status = request(path, method, data, authenticated=authenticated)[0]
                except urllib.error.HTTPError as error:
                    status = error.code
                    error.close()
                checked(status == expected, f"{method} {path}: HTTP {expected}")

            def login():
                json_request("/api/auth/login", "POST", {"username": "admin", "pass" + "word": credential})
                checked(json_request("/api/auth/me")["username"] == "admin", "administrator can sign in")

            def start(log):
                nonlocal process
                process = subprocess.Popen(
                    [str(binary)], cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
                )
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise AssertionError(f"server exited before health check: {process.returncode}")
                    try:
                        if request("/api/health")[0] == 200:
                            break
                    except (urllib.error.URLError, TimeoutError):
                        pass  # Startup has not opened the listener yet; retry within the bounded deadline.
                    time.sleep(0.25)
                else:
                    raise AssertionError("server health check did not pass within 90 seconds")
                result = subprocess.run([str(binary), "health"], cwd=root, env=env, capture_output=True, timeout=15)
                checked(result.returncode == 0, "direct startup and built-in health subcommand succeed")

            with (evidence / "startup.jsonl").open("wb") as log:
                start(log)
                html = request("/")[2].decode()
                checked('<div id="root"' in html, "embedded frontend page is served")
                assets = Assets()
                assets.feed(html)
                checked(any(path.endswith(".js") for path in assets.paths), "HTML references an embedded JavaScript bundle")
                for path in sorted(assets.paths | {"/office-frame.js", "/zh-CN.js"}):
                    _, headers, body = request(path)
                    checked(bool(body) and "text/html" not in headers.get("Content-Type", ""), f"embedded resource is served: {path}")
                expect_status("/api/auth/me", 401, authenticated=False)
                expect_status("/api/auth/login", 401, "POST", {"username": "admin", "pass" + "word": "incorrect"}, authenticated=False)
                login()
                expect_status("/api/folders", 400, "POST", {"parent_id": "missing", "name": "../invalid"})
                expect_status("/api/files/missing/content", 404)
                root_id = json_request("/api/auth/me")["root_id"]
                name = "麒麟 ARM64.txt"
                metadata = ",".join(f"{key} {base64.b64encode(value.encode()).decode()}" for key, value in {"filename": name, "parentId": root_id}.items())
                _, headers, _ = request("/api/uploads", "POST", b"", {"Tus-Resumable": "1.0.0", "Upload-Length": "0", "Upload-Metadata": metadata})
                node_id = headers["X-Node-Id"]
                checked(bool(node_id), "upload creates a file with a Chinese filename")
                payload = "ARM64 standalone round trip\n中文内容\n".encode()
                request(f"/api/files/{node_id}/content", "PUT", payload, {"Content-Type": "application/octet-stream"})
                checked(request(f"/api/files/{node_id}/content")[2] == payload, "download bytes match uploaded content")
                checked((root / "data/blobs/users/admin" / name).read_bytes() == payload, "file contents are stored on disk")
                branding = json_request("/api/branding")
                branding["site_name"] = "ARM64 persistence check"
                json_request("/api/admin/branding", "PUT", branding)
                checked(json_request("/api/branding")["site_name"] == branding["site_name"], "configuration change is saved")
                stop()
            with (evidence / "restart.jsonl").open("wb") as log:
                start(log)
                cookies.clear()
                login()
                checked(request(f"/api/files/{node_id}/content")[2] == payload, "file contents survive a restart")
                checked(json_request("/api/branding")["site_name"] == branding["site_name"], "configuration survives a restart")
                checked((root / "data/secret.key").is_file(), "persistent encryption key exists in the data directory")
                stop()
            for filename in ["startup.jsonl", "restart.jsonl"]:
                log_text = (evidence / filename).read_text(encoding="utf-8")
                checked('"Stopped"' in log_text, f"graceful shutdown is recorded in {filename}")
            records = [json.loads(line) for line in (evidence / "startup.jsonl").read_text(encoding="utf-8").splitlines() if line.startswith("{")]
            versions = [record.get("fields", {}).get("sqlite_version_number", 0) for record in records]
            checked(any(version >= 3054000 for version in versions), "linked SQLite runtime passes the patched-version check")
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        (evidence / "smoke-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
