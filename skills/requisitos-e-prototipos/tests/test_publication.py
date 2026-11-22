import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from publication import locked_output, publish
from interface_review import prepare_review


def windows_dacl(file, snapshot):
    # /save emits the relative filename and its DACL in SDDL, independent of the console language.
    snapshot.unlink(missing_ok=True)
    subprocess.run(["icacls.exe", file.name, "/save", str(snapshot), "/q"], cwd=file.parent,
                   capture_output=True, check=True, timeout=10)
    records = snapshot.read_text(encoding="utf-16-le").splitlines()
    if len(records) != 2 or records[0].lstrip("\ufeff") != file.name or not records[1].startswith("D:"):
        raise AssertionError(f"Formato inesperado de DACL para {file}")
    return records[1]


class PublicationTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name) / "prototipo"
        self.project.mkdir()
        self.before = {"p.html": "antigo", "p-SPEC.md": "anterior", "resultado.json": "{}"}
        self.after = {"p.html": "atualizado", "p-SPEC.md": "atualizada", "resultado.json": '{"versao":2}'}

    def read_outputs(self):
        return {p.name: p.read_text(encoding="utf8") for p in (self.project / "dist").iterdir()}

    def test_failure_on_last_replace_restores_all_files_and_allows_retry(self):
        replace = Path.replace
        def fail_on_report(src, dest):
            if src.name == "next" and dest.name == "resultado.json":
                raise PermissionError("relatório bloqueado")
            return replace(src, dest)

        with locked_output(self.project) as output:
            publish(output, self.before)
            with patch.object(Path, "replace", fail_on_report), self.assertRaises(PermissionError):
                publish(output, self.after)
            self.assertEqual(self.read_outputs(), self.before)
            publish(output, self.after)
            self.assertEqual(self.read_outputs(), self.after)

    def test_interrupted_initial_and_repeat_publications_recover_under_next_lock(self):
        worker = """
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from publication import locked_output, publish
replace = Path.replace
def die_after_html(src, dest):
    result = replace(src, dest)
    if src.name == 'next' and dest.suffix == '.html':
        os._exit(45)
    return result
Path.replace = die_after_html
with locked_output(Path(sys.argv[2])) as output:
    publish(output, {'p.html': 'parcial', 'p-SPEC.md': 'parcial'})
"""
        for previous in ({}, self.before):
            with self.subTest(existing=bool(previous)):
                with locked_output(self.project) as output:
                    publish(output, previous)
                run = subprocess.run([sys.executable, "-c", worker, str(SKILL / "scripts"), str(self.project)], timeout=10)
                self.assertEqual(run.returncode, 45)
                with locked_output(self.project):
                    self.assertEqual(self.read_outputs(), previous)

    def run_cli(self, expected=0, command="build"):
        env = dict(os.environ, PYTHONIOENCODING="ascii", PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, str(SKILL / "scripts/viewer.py"), command, str(self.project)],
                                capture_output=True, encoding="utf8", env=env, timeout=30)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def write_json(self, name, data):
        (self.project / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf8")

    def complete_fixture_review(self):
        review = json.loads((self.project / "interface-review.json").read_text(encoding="utf8"))
        for screen in review["screens"]:
            for row in screen["principles"]:
                row.update(status="passed", evidence=f"{row['principle']} inspecionado no teste da publicação. PRIVATE_MARKER_REVIEW")
            screen["browser"] = {"flow": screen["flow"], "version": screen["version"], "violations": [],
                                 "checks": {"transition_properties": True, "will_change": True, "hit_area": True}}
        self.write_json("interface-review.json", review)

    def setup_brief(self):
        shutil.copytree(SKILL / "assets/viewer/starter", self.project, dirs_exist_ok=True)
        statement = "Mostrar a escolha e aguardar a decisão."
        private_source = self.project / "PRIVATE_MARKER_FOLDER/pedido.txt"
        private_source.parent.mkdir()
        private_source.write_text(statement, encoding="utf8")
        self.write_json("sources.json", {"sources": [{"name": "pedido", "path": str(private_source)}]})
        evidence = {"source": "pedido", "location": "linha 1", "excerpt": statement}
        requirements = [{"id": flow, "description": statement, "acceptance": "Escolha visível.",
                         "flow": flow, "evidence": [evidence]} for flow in ("briefing", "review")]
        delivery = {"schema_version": "1.0", "requirements": requirements, "assumptions": [],
                    "limitations": [], "simulations": [], "open_questions": []}
        self.write_json("delivery.json", delivery)
        return delivery

    def test_internal_markers_at_every_level_stay_out_of_all_artifacts(self):
        delivery = self.setup_brief()
        project = json.loads((self.project / "project.json").read_text(encoding="utf8"))
        persona = {field: "A" for field in ("name", "tag", "color", "ini", "line", "quote", "needs")}
        project["personas"] = {"leitor": persona}
        question = {"kind": "gap", "question": "Qual decisão tomar?", "evidence": [dict(delivery["requirements"][0]["evidence"][0])]}
        delivery["open_questions"] = [question]
        private = [project, project["flows"][0], project["navigation"][0], persona, delivery,
                   delivery["requirements"][0], delivery["requirements"][0]["evidence"][0],
                   question, question["evidence"][0]]
        for index, item in enumerate(private):
            item["anotacao_interna"] = f"PRIVATE_MARKER_{index}"
        self.write_json("project.json", project)
        self.write_json("delivery.json", delivery)
        self.assertEqual(self.run_cli()["readiness"], "draft")
        self.complete_fixture_review()
        report = self.run_cli(command="finalize")
        for artifact in report["artifacts"].values():
            content = Path(artifact).read_bytes()
            self.assertNotIn(b"PRIVATE_MARKER_", content, artifact)
            self.assertIn(b"Mostrar a escolha", content, artifact)

    def test_private_paths_and_invalid_public_types_fail_before_sharing(self):
        delivery = self.setup_brief()
        ref = delivery["requirements"][0]["evidence"][0]
        for path in (r"C:\Usuarios\PRIVATE_MARKER\pedido.txt", "/home/PRIVATE_MARKER/pedido.txt", "file:pedido.txt"):
            ref["source"] = path
            self.write_json("delivery.json", delivery)
            self.assertIn("nome público", self.run_cli(1)["errors"][0])
        ref["source"] = "pedido"
        delivery["requirements"][0]["description"] = {"private": "PRIVATE_MARKER"}
        self.write_json("delivery.json", delivery)
        self.assertIn("description", self.run_cli(1)["errors"][0])
        self.assertEqual(self.read_outputs(), {})

    def test_drafts_and_stale_reviews_cannot_replace_an_approved_delivery(self):
        self.setup_brief()
        draft = self.run_cli()
        self.assertEqual(draft["readiness"], "draft")
        self.assertEqual(self.run_cli(1, "finalize")["readiness"], "not_ready")
        self.assertEqual(self.read_outputs(), {})
        self.complete_fixture_review()
        approved = self.run_cli(command="finalize")
        self.assertEqual(approved["readiness"], "ready")
        before = self.read_outputs()
        review_path = self.project / "interface-review.json"
        first_review = review_path.read_bytes()
        with (self.project / "styles.css").open("a", encoding="utf8") as css:
            css.write("\n.ph .novo { color: inherit; }\n")
        self.assertIn("mudou", self.run_cli(1, "finalize")["errors"][0])
        self.run_cli()
        new_review = review_path.read_bytes()
        self.assertNotEqual(new_review, first_review)
        review_path.write_bytes(first_review)
        self.assertIn("não corresponde", self.run_cli(1, "finalize")["errors"][0])
        self.assertEqual(self.read_outputs(), before)
        review_path.write_bytes(new_review)
        self.complete_fixture_review()
        self.assertNotEqual(self.run_cli(command="finalize")["html_sha256"], approved["html_sha256"])

    def test_concurrent_build_fails_cleanly(self):
        with locked_output(self.project) as output:
            publish(output, self.before)
            report = self.run_cli(expected=1)
            self.assertIn("Outra geração", report["errors"][0])
            self.assertEqual(self.read_outputs(), self.before)

    @unittest.skipUnless(os.name == "nt", "Confere as permissões herdadas no NTFS.")
    def test_published_files_and_reviews_inherit_their_destination_permissions(self):
        # Create like a normal shared workspace, rather than the owner-only TemporaryDirectory.
        shared = Path(tempfile.gettempdir()) / f"viewer-test-{uuid.uuid4().hex}"
        shared.mkdir()
        self.addCleanup(shutil.rmtree, shared)
        self.project = shared
        with locked_output(self.project) as output:
            publish(output, self.before)
            publish(output, self.after)
            review = prepare_review(self.project, {"html_sha256": "first"})
            prepare_review(self.project, {"html_sha256": "next"})
        files = [*output.iterdir(), review, *review.parent.glob(".viewer-build/reviews/*.json")]
        self.assertEqual(len(files), 5)
        with tempfile.TemporaryDirectory() as temp:
            snapshot = Path(temp) / "acl.txt"
            for file in files:
                sample = file.parent / "controle-de-permissoes.txt"
                sample.touch()
                with self.subTest(file=file.name):
                    self.assertEqual(windows_dacl(file, snapshot), windows_dacl(sample, snapshot))

    @unittest.skipUnless(os.name == "nt", "Reproduz compartilhamento de arquivo específico do Windows.")
    def test_windows_locked_spec_preserves_approved_delivery(self):
        from ctypes import wintypes

        self.setup_brief()
        self.run_cli()
        self.complete_fixture_review()
        report = self.run_cli(command="finalize")
        paths = {key: Path(path) for key, path in report["artifacts"].items()}
        before = {key: path.read_bytes() for key, path in paths.items()}
        config = json.loads((self.project / "project.json").read_text(encoding="utf8"))
        config["name"] += " Revisão"
        self.write_json("project.json", config)
        self.run_cli()
        self.complete_fixture_review()
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                       wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateFileW(str(paths["spec"]), 0x80000000, 1, None, 3, 0, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        try:
            failed = self.run_cli(expected=1, command="finalize")
            self.assertEqual(failed["status"], "failed")
            self.assertEqual({key: path.read_bytes() for key, path in paths.items()}, before)
        finally:
            kernel.CloseHandle(handle)
        self.run_cli(command="finalize")
        self.assertNotEqual(paths["html"].read_bytes(), before["html"])
