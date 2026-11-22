import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).resolve().parents[1] / "scripts/viewer.py"
EXCERPT = 'A etiqueta de encerramento é </script>. Manter "nome & código" na prévia.'


class BuildTraceTest(unittest.TestCase):
    def setUp(self):
        working = tempfile.TemporaryDirectory()
        self.addCleanup(working.cleanup)
        self.project = Path(working.name) / "exemplo"
        self.run_viewer("init")
        self.delivery_file = self.project / "delivery.json"
        self.delivery = json.loads(self.delivery_file.read_text(encoding="utf-8"))
        (self.project / "briefing.txt").write_text(EXCERPT, encoding="utf-8")
        (self.project / "sources.json").write_text(json.dumps({
            "sources": [{"name": "briefing.txt", "path": "briefing.txt"}]
        }), encoding="utf-8")
        self.delivery["requirements"] = [
            {
                "id": "RF-" + flow,
                "description": "Mostrar a etiqueta no fluxo " + flow,
                "flow": flow,
                "acceptance": "A etiqueta tem o mesmo texto do briefing.",
                "evidence": [{"source": "briefing.txt", "location": "linha 1", "excerpt": EXCERPT}],
            }
            for flow in ("briefing", "review")
        ]

    def run_viewer(self, command, expected_exit=0):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run(
            [sys.executable, str(CLI), command, str(self.project)],
            capture_output=True, encoding="utf-8", env=env, timeout=60,
        )
        self.assertEqual(result.returncode, expected_exit, result.stderr + result.stdout)
        return json.loads(result.stdout)

    def build(self, expected_exit=0):
        self.delivery_file.write_text(json.dumps(self.delivery, ensure_ascii=False), encoding="utf-8")
        return self.run_viewer("build", expected_exit)

    def test_export_matches_spec_and_keeps_quoted_markup_inside_project_data(self):
        report = self.build()
        self.assertEqual(report["status"], "succeeded")
        html = Path(report["artifacts"]["html"]).read_text(encoding="utf-8")
        spec = Path(report["artifacts"]["spec"]).read_text(encoding="utf-8")
        block = re.search(r'<script[^>]+id="prototype-project"[^>]*>(.*?)</script\s*>', html, re.I | re.S)
        self.assertIsNotNone(block)
        project = json.loads(block.group(1))
        self.assertNotIn(EXCERPT, html)
        self.assertEqual(project["delivery"]["requirements"], self.delivery["requirements"])
        self.assertIn(EXCERPT, spec)
        self.assertEqual(project["specMarkdown"], spec)

    def assert_no_delivery(self, report, diagnostic):
        self.assertEqual(report["status"], "failed")
        self.assertIn(diagnostic, " ".join(report["errors"]))
        for kind in ("html", "spec"):
            self.assertNotIn(kind, report["artifacts"])

    def test_build_rejects_requirement_without_evidence(self):
        self.delivery["requirements"][0]["evidence"] = []
        self.assert_no_delivery(self.build(expected_exit=1), "evidence")

    def test_build_rejects_flow_without_requirement(self):
        self.delivery["requirements"].pop()
        self.assert_no_delivery(self.build(expected_exit=1), "Fluxo sem requisito documentado: review")


if __name__ == "__main__":
    unittest.main()
