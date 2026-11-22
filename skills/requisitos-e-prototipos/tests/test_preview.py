import http.client
from contextlib import redirect_stdout
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch
from urllib.request import urlopen
from urllib.parse import urlsplit


PREVIEW = Path(__file__).resolve().parents[1] / "scripts" / "preview.py"
SPEC = spec_from_file_location("viewer_preview", PREVIEW)
preview = module_from_spec(SPEC)
SPEC.loader.exec_module(preview)


class PreviewTest(unittest.TestCase):
    def test_opens_standalone_file_even_when_ide_cannot_launch_a_server(self):
        with TemporaryDirectory() as directory:
            html = Path(directory).resolve() / "viewer.html"
            html.write_text("<title>Reserva</title>", encoding="utf-8")
            output = StringIO()
            with patch.object(preview, "launch_preview", side_effect=OSError("indisponível")), \
                 patch.object(preview, "open_external", return_value=True) as external, redirect_stdout(output):
                preview.present(html, 3600, True)
            external.assert_called_once_with(html.as_uri())
            delivery = json.loads(output.getvalue())
            self.assertIsNone(delivery["preview_url"])
            self.assertEqual(delivery["preview_error"], "indisponível")
            self.assertEqual(delivery["html"], str(html))
            self.assertTrue(delivery["external_requested"])

    def test_delivery_survives_its_launcher_and_file_survives_preview_expiration(self):
        with TemporaryDirectory() as directory:
            html = Path(directory) / "espaço e #ação.html"
            content = b"<title>Reserva confirmada</title>"
            html.write_bytes(content)
            command = [sys.executable, str(PREVIEW), str(html), "--launch", "--idle-seconds", "2"]
            finished = subprocess.run(command, capture_output=True, text=True, timeout=15, check=True)
            delivery = json.loads(finished.stdout)
            self.assertEqual(delivery["html"], str(html.resolve()))
            self.assertEqual(delivery["file_url"], html.resolve().as_uri())
            with urlopen(delivery["preview_url"], timeout=3) as response:
                self.assertEqual(response.read(), content)
            time.sleep(4.3)
            with self.assertRaises(OSError):
                urlopen(delivery["preview_url"], timeout=3)
            with urlopen(delivery["file_url"]) as response:
                self.assertEqual(response.read(), content)

    def test_only_selected_html_is_available(self):
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            html = folder / "prévia reservada.html"
            content = "<title>Fluxos e requisitos</title>".encode("utf-8")
            html.write_bytes(content)
            for name in ["regras.pdf", "resultado.json", "outro.html"]:
                (folder / name).write_bytes(b"documento reservado")
            with subprocess.Popen([sys.executable, str(PREVIEW), str(html)],
                                  stdout=subprocess.PIPE, text=True) as server:
                try:
                    url = urlsplit(server.stdout.readline().strip())
                    self.assertEqual(url.hostname, "127.0.0.1")
                    client = http.client.HTTPConnection(url.hostname, url.port, timeout=5)
                    self.addCleanup(client.close)
                    for method, expected in [("GET", content), ("HEAD", b"")]:
                        client.request(method, url.path + "?flow=home")
                        response = client.getresponse()
                        self.assertEqual(response.status, 200)
                        self.assertEqual(int(response.getheader("Content-Length")), len(content))
                        self.assertEqual(response.read(), expected)
                    for path in ["/", "/regras.pdf", "/resultado.json", "/outro.html"]:
                        client.request("GET", path)
                        response = client.getresponse()
                        self.assertEqual(response.status, 404)
                        self.assertNotIn(b"documento reservado", response.read())
                finally:
                    server.terminate()


if __name__ == "__main__":
    unittest.main()
