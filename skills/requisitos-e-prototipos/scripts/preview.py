"""Open the standalone HTML and provide a local preview for the IDE."""

import argparse
import http.client
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import time
from urllib.parse import urlsplit
import webbrowser


ROUTE = "/viewer.html"


def handler_for(html):
    class ViewerHandler(BaseHTTPRequestHandler):
        def do_HEAD(self):
            if urlsplit(self.path).path != ROUTE:
                self.send_error(HTTPStatus.NOT_FOUND)
                return False
            self.server.last_read = time.monotonic()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            return True

        def do_GET(self):
            if self.do_HEAD():
                self.wfile.write(html)

        def log_message(self, format, *args):
            # Keep stdout reserved for the URL consumed by the IDE.
            pass

    return ViewerHandler


def open_external(url):
    try:
        if webbrowser.open(url, new=2):
            return True
    except (OSError, webbrowser.Error) as exc:
        print(exc, file=sys.stderr)
    print("Abra o arquivo HTML no navegador externo.", file=sys.stderr, flush=True)
    return False


def serve(html, ready=None, idle_seconds=3600, open_browser=False):
    with ThreadingHTTPServer(("127.0.0.1", 0), handler_for(html.read_bytes())) as server:
        url = f"http://127.0.0.1:{server.server_port}{ROUTE}"
        server.last_read = time.monotonic()
        if ready is None:
            print(url, flush=True)
            if open_browser:
                Thread(target=open_external, args=(url,), daemon=True).start()
            server.serve_forever()
            return
        pending = ready.with_suffix(".tmp")
        pending.write_text(url, encoding="ascii")
        pending.replace(ready)
        server.timeout = min(5, idle_seconds)
        while time.monotonic() - server.last_read < idle_seconds:
            server.handle_request()


def verified_url(ready, child, size):
    deadline = time.monotonic() + 8
    while not ready.exists():
        if child.poll() is not None or time.monotonic() >= deadline:
            raise OSError("O servidor local não iniciou.")
        time.sleep(0.05)
    url = ready.read_text(encoding="ascii")
    address = urlsplit(url)
    connection = http.client.HTTPConnection(address.hostname, address.port, timeout=3)
    try:
        connection.request("HEAD", ROUTE)
        reply = connection.getresponse()
        if reply.status != 200 or reply.getheader("Content-Length") != str(size):
            raise OSError("A prévia local não corresponde ao arquivo.")
    finally:
        connection.close()
    return url


def launch_preview(html, idle_seconds):
    options = {"start_new_session": True}
    if os.name == "nt":
        options = {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP}
    with TemporaryDirectory(prefix="viewer-inicio-") as temp:
        ready = Path(temp) / "url.txt"
        command = [sys.executable, str(Path(__file__).resolve()), str(html), "--ready", str(ready),
                   "--idle-seconds", str(idle_seconds)]
        child = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, close_fds=True, **options)
        try:
            return verified_url(ready, child, html.stat().st_size)
        except (OSError, http.client.HTTPException):
            if child.poll() is None:
                child.terminate()
            child.wait(timeout=5)
            raise


def present(html, idle_seconds, open_browser):
    result = {"html": str(html), "file_url": html.as_uri(), "preview_url": None}
    if open_browser:
        result["external_requested"] = open_external(html.as_uri())
    try:
        result["preview_url"] = launch_preview(html, idle_seconds)
    except (OSError, http.client.HTTPException, subprocess.SubprocessError) as exc:
        result["preview_error"] = str(exc)
    print(json.dumps(result, ensure_ascii=True), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path, help="HTML gerado pelo viewer")
    parser.add_argument("--open", action="store_true", help="Abrir no navegador padrão")
    parser.add_argument("--launch", action="store_true", help="Entregar o HTML e iniciar prévia independente da IDE")
    parser.add_argument("--idle-seconds", type=int, default=3600, help="Duração da prévia da IDE após a última leitura")
    parser.add_argument("--ready", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.html.is_file() or args.html.suffix.lower() not in (".html", ".htm"):
        parser.error("Informe o caminho de um arquivo HTML.")
    if args.idle_seconds < 1:
        parser.error("A duração da prévia deve ser positiva.")
    try:
        html = args.html.resolve()
        if args.launch:
            present(html, args.idle_seconds, args.open)
        else:
            serve(html, args.ready, args.idle_seconds, args.open)
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        parser.exit(1, f"Não foi possível abrir a prévia: {exc}\n")


if __name__ == "__main__":
    main()
