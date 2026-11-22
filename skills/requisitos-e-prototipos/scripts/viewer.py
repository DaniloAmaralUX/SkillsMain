#!/usr/bin/env python3
"""Initialize or build a portable viewer project using only this skill's files."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from evidence import validate_evidence
from interface_review import prepare_review, template, validate_review
from publication import locked_output, publish
from public_data import public_delivery, public_project
from source_check import verify_sources
from trace_spec import trace_spec

SKILL = Path(__file__).resolve().parents[1]
ASSETS = SKILL / "assets/viewer"
BUILD_ERRORS = (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError)


def load_builder():
    spec = importlib.util.spec_from_file_location("portable_viewer", ASSETS / "template/build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def workspace_path(value):
    path = Path(value).resolve()
    if path == SKILL or SKILL in path.parents:
        raise ValueError("Crie o protótipo na pasta do projeto, fora da instalação da skill.")
    return path


def initialize(directory):
    sources = ["project.json", "screens.js", "styles.css", "delivery.json", "sources.json"]
    conflicts = [name for name in sources if (directory / name).exists()]
    if conflicts:
        raise ValueError("Arquivos já existentes; nada foi sobrescrito: " + ", ".join(conflicts))
    project = json.loads((ASSETS / "starter/project.json").read_text(encoding="utf-8"))
    project["id"] = re.sub(r"[^a-z0-9_-]+", "-", directory.name.lower()).strip("-") or "prototipo"
    project["name"] = directory.name
    directory.mkdir(parents=True, exist_ok=True)
    for name in sources[1:]:
        shutil.copyfile(ASSETS / "starter" / name, directory / name)
    (directory / "project.json").write_text(json.dumps(project, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "initialized", "project": str(directory), "files": sources}


def delivery_context(directory, project):
    path = directory / "delivery.json"
    if not path.is_file():
        raise ValueError("Adicione delivery.json com requisitos e origens.")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or data.get("schema_version") != "1.0":
        raise ValueError("delivery.json precisa de schema_version 1.0.")
    for key in ("assumptions", "simulations", "limitations"):
        if not isinstance(data.get(key), list) or any(not isinstance(x, str) or not x.strip() for x in data[key]):
            raise ValueError(f"delivery.json: {key} deve ser uma lista de textos.")
    validate_evidence(data, flow_ids=[flow["id"] for flow in project["flows"]])
    context = public_delivery(data)
    verify_sources(directory, context)
    return context


def check_javascript(node, paths):
    for path in paths:
        result = subprocess.run([node, "--check", str(path)], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=30)
        if result.returncode:
            raise ValueError(f"JavaScript inválido em {path.name}:\n{result.stderr}")


def render(directory):
    node = shutil.which("node")
    if not node:
        raise ValueError("Node é necessário para verificar as telas e extrair os requisitos. Instale Node e tente novamente.")
    builder = load_builder()
    project = public_project(builder.load_project(directory / "project.json"))
    screens = directory / "screens.js"
    if not screens.is_file():
        raise ValueError("Adicione screens.js ao lado de project.json.")
    scripts = list((ASSETS / "template/src").glob("*.js")) + [screens]
    check_javascript(node, scripts)
    registry = builder.extract_versions_metadata(project, screens)
    missing = [flow["id"] for flow in project["flows"] if not registry.get(flow["id"])]
    if missing:
        raise ValueError("Fluxos sem versão válida ou erro no registro das telas: " + ", ".join(missing))
    context = delivery_context(directory, project)
    styles = directory / "styles.css"
    spec = builder.render_spec_markdown(project, screens) + trace_spec(context)
    project["delivery"] = context
    project["specMarkdown"] = spec
    html = builder.build(directory / "project.json", screens, styles if styles.is_file() else None, project)
    return project["id"], context, html, spec, template(html, registry)


def generate(directory, output, finalize):
    project_id, context, html, spec, expected = render(directory)
    state = directory / ".viewer-build"
    draft = state / "draft"
    draft.mkdir(exist_ok=True)
    names = {"html": f"{project_id}.html", "spec": f"{project_id}-SPEC.md", "report": "resultado.json"}
    if finalize:
        for key, content in (("html", html), ("spec", spec)):
            staged = draft / names[key]
            if not staged.is_file() or staged.read_bytes() != content.encode("utf-8"):
                raise ValueError("A entrega mudou. Execute build e revise o rascunho atual antes de finalizar.")
        validate_review(directory / "interface-review.json", expected)
    else:
        output = draft
        prepare_review(directory, expected)
    readiness = "ready" if finalize else "draft"
    report = {"schema_version": "1.0", "status": "succeeded", "exit_code": 0,
              "readiness": readiness, "html_sha256": expected["html_sha256"],
              "project": str(directory), "artifacts": {key: str(output / name) for key, name in names.items()},
              "declared_context": context,
              "checks": {"syntax": "passed", "registry": "passed", "sources": "passed", "build": "passed"},
              "human_review": {"status": "not_run", "reason": "Verifique as interações no navegador separadamente."},
              "errors": []}
    report["checks"]["interface_review"] = "passed" if finalize else "pending"
    if not finalize:
        report["review_file"] = str(directory / "interface-review.json")
    contents = {names["html"]: html, names["spec"]: spec, names["report"]: json_text(report)}
    publish(output, contents, state if finalize else state / "draft-transaction")
    return report


def json_text(report):
    return json.dumps(report, ensure_ascii=False, indent=2) + "\n"


def failure(error):
    return {"status": "failed", "exit_code": 1, "artifacts": {}, "errors": [str(error)]}


def can_record_failure(path):
    if not path.exists():
        return True
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("status") == "failed"
    except (OSError, ValueError, AttributeError):
        return False


def build_project(directory, finalize=False):
    with locked_output(directory) as output:
        try:
            return generate(directory, output, finalize)
        except BUILD_ERRORS as error:
            report = failure(error)
            report["readiness"] = "not_ready"
            draft = directory / ".viewer-build/draft"
            path = draft / "resultado.json"
            state = draft.parent / "draft-transaction"
            if not finalize and can_record_failure(path) and not (state / "pending").exists():
                report["artifacts"]["report"] = str(path)
                try:
                    draft.mkdir(exist_ok=True)
                    publish(draft, {path.name: json_text(report)}, state)
                except BUILD_ERRORS as write_error:
                    report["artifacts"].clear()
                    report["errors"].append(str(write_error))
            return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "build", "finalize"))
    parser.add_argument("project", help="Pasta do protótipo no projeto de destino")
    args = parser.parse_args(argv)
    try:
        directory = workspace_path(args.project)
        report = initialize(directory) if args.command == "init" else build_project(directory, args.command == "finalize")
    except BUILD_ERRORS as error:
        report = failure(error)
    print(json.dumps(report, ensure_ascii=True))
    return report.get("exit_code", 0)


if __name__ == "__main__":
    raise SystemExit(main())
