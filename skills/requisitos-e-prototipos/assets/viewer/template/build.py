#!/usr/bin/env python3
"""Build one portable HTML, or validate inputs without writing output."""
import argparse
import base64
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"


def validate_project(value):
    if not isinstance(value, dict):
        raise ValueError("O projeto deve ser um objeto JSON.")
    project = dict(value)
    for key in ("id", "name"):
        if not isinstance(project.get(key), str) or not project[key].strip():
            raise ValueError(f"Preencha '{key}' no projeto.")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", project["id"]):
        raise ValueError("Use apenas letras, números, hífen ou sublinhado no id do projeto.")
    flows = project.get("flows")
    if not isinstance(flows, list) or not flows:
        raise ValueError("Adicione pelo menos um fluxo em 'flows'.")
    ids, normalized = set(), []
    for flow in flows:
        if not isinstance(flow, dict) or not all(isinstance(flow.get(k), str) and flow[k].strip() for k in ("id", "title")):
            raise ValueError("Cada fluxo precisa de id e title preenchidos.")
        if flow["id"] in ids:
            raise ValueError(f"O fluxo '{flow['id']}' está duplicado. Use ids únicos.")
        ids.add(flow["id"])
        item = {"sum": "", "today": [], **flow}
        if not isinstance(item["sum"], str) or not isinstance(item["today"], list) or not all(valid_today(x) for x in item["today"]):
            raise ValueError(f"No fluxo '{flow['id']}', today deve conter textos ou objetos com src e cap preenchidos.")
        normalized.append(item)
    project["flows"] = normalized
    navigation = project.setdefault("navigation", [])
    if not isinstance(navigation, list):
        raise ValueError("navigation deve ser uma lista.")
    nav_ids = set()
    for tab in navigation:
        if not isinstance(tab, dict) or not all(isinstance(tab.get(k), str) and tab[k].strip() for k in ("id", "label", "flow")):
            raise ValueError("Cada item de navigation precisa de id, label e flow.")
        if tab["id"] in nav_ids:
            raise ValueError(f"O item de navegação '{tab['id']}' está duplicado.")
        nav_ids.add(tab["id"])
        if tab["flow"] not in ids:
            raise ValueError(f"A navegação '{tab['id']}' aponta para o fluxo inexistente '{tab['flow']}'. Corrija flow.")
        version = tab.get("version", 0)
        if type(version) is not int or version < 0:
            raise ValueError(f"Use uma versão inteira a partir de zero em navigation.{tab['id']}.")
    personas = project.setdefault("personas", {})
    if not isinstance(personas, dict):
        raise ValueError("personas deve ser um objeto.")
    for key, persona in personas.items():
        fields = ("name", "tag", "color", "ini", "line", "quote", "needs")
        if not isinstance(persona, dict) or not all(isinstance(persona.get(k), str) for k in fields):
            raise ValueError(f"Preencha os textos name, tag, color, ini, line, quote e needs da persona '{key}'.")
    if project.get("uiSdk"):
        raise ValueError("Esta versão usa apenas o Kit incluído no viewer.")
    return project


def valid_today(item):
    return isinstance(item, str) or (isinstance(item, dict) and set(item) == {"src", "cap"}
        and all(isinstance(item[k], str) and item[k].strip() for k in ("src", "cap")))


def embed_today_images(project, project_path):
    """Embed local raster references relative to the project configuration."""
    flows = project["flows"]
    project = {**project, "flows": []}
    formats = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
    base = Path(project_path).resolve().parent
    for flow in flows:
        entries = []
        for item in flow["today"]:
            if isinstance(item, str):
                entries.append(item)
                continue
            path = (base / item["src"]).resolve()
            if not path.is_relative_to(base) or path.suffix.lower() not in formats:
                raise ValueError("Imagem de today deve estar na pasta do projeto e ser PNG, JPEG, WebP ou GIF.")
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            entries.append({"src": f"data:{formats[path.suffix.lower()]};base64,{encoded}", "cap": item["cap"]})
        project["flows"].append({**flow, "today": entries})
    return project
def script_safe(text):
    return re.sub(r"</script", lambda m: "<\\/" + m.group()[2:], text, flags=re.IGNORECASE)


def load_project(project_path=ROOT / "project.json"):
    """Read and validate a project.json file once."""
    return validate_project(json.loads(Path(project_path).read_text(encoding="utf-8-sig")))


def extract_versions_metadata(project, screens_path):
    """Extract registered version metadata from screens.js using Node VM when available."""
    node = shutil.which("node")
    if not node or not screens_path or not Path(screens_path).is_file():
        return {}
    runner = (
        "const fs=require('node:fs'),vm=require('node:vm');"
        "const proj=JSON.parse(fs.readFileSync(0,'utf8'));"
        "const kit=fs.readFileSync(process.argv[1],'utf8');"
        "const shell=fs.readFileSync(process.argv[2],'utf8');"
        "const screens=fs.readFileSync(process.argv[3],'utf8');"
        "const ctx={addEventListener(){},"
        "document:{getElementById:()=>({textContent:JSON.stringify(proj)}),addEventListener(){}},localStorage:{getItem:()=>null,setItem(){}},"
        "location:{search:''},matchMedia:()=>({matches:false}),URLSearchParams,console};"
        "ctx.window=ctx;"
        "vm.runInNewContext(kit,ctx);vm.runInNewContext(shell,ctx);vm.runInNewContext(screens,ctx);"
        "const out={};for(const [k,list] of Object.entries(ctx.Proto.registry)){"
        "out[k]=list.map(v=>({name:v.name,axis:v.axis||'',personas:v.personas||[],fixes:v.fixes||[],tryThis:v.tryThis||[],motion:v.motion||'',tradeoff:v.tradeoff||''}));}"
        "process.stdout.write(JSON.stringify(out));"
    )
    try:
        res = subprocess.run(
            [node, "-e", runner, str(SRC / "kit.js"), str(SRC / "shell.js"), str(screens_path)],
            input=json.dumps(project), capture_output=True, text=True, check=True, timeout=15, encoding="utf-8"
        )
        return json.loads(res.stdout)
    except Exception:
        return {}


def render_spec_markdown(project, screens_path=None):
    """Render a traceability SPEC.md summary from a validated project dict and optional screens.js."""
    registry = extract_versions_metadata(project, screens_path)
    personas = project.get("personas", {})
    lines = [f"# {project['name']}", "", f"- **ID:** `{project['id']}`", f"- **Fluxos:** {len(project['flows'])}", ""]
    for idx, flow in enumerate(project["flows"], start=1):
        lines.append(f"## {idx:02d}. {flow['title']} (`{flow['id']}`)")
        if flow.get("sum"):
            lines.extend(["", flow["sum"]])
        if flow.get("today"):
            lines.extend(["", "- **Experiência atual:**", *[f"  - {item if isinstance(item, str) else item['cap']}" for item in flow["today"]]])
        for v_idx, ver in enumerate(registry.get(flow["id"], []), start=1):
            lines.extend(["", f"### Versão {v_idx}: {ver['name']}"])
            if ver.get("axis"):
                lines.append(f"- **Proposta:** {ver['axis']}")
            if ver.get("personas"):
                names = ", ".join(personas.get(pid, {}).get("name", pid) for pid in ver["personas"])
                lines.append(f"- **Personas:** {names}")
            if ver.get("fixes"):
                lines.extend(["- **Problemas que resolve:**", *[f"  - {item}" for item in ver["fixes"]]])
            if ver.get("tryThis"):
                lines.extend(["- **Experimente:**", *[f"  - {item}" for item in ver["tryThis"]]])
            if ver.get("motion"):
                lines.append(f"- **Animação:** {ver['motion']}")
            if ver.get("tradeoff"):
                lines.append(f"- **Pontos de atenção:** {ver['tradeoff']}")
        lines.append("")
    if personas:
        lines.extend(["## Personas", ""])
        for pid, persona in personas.items():
            lines.append(f"- **{persona['name']}** (`{pid}` · {persona['tag']}): {persona['needs']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build(project_path=ROOT / "project.json", screens_path=SRC / "screens/screens.js", styles_path=None, project=None):
    data = validate_project(project) if project is not None else load_project(project_path)
    data = embed_today_images(data, project_path)
    read = lambda path: (SRC / path).read_text(encoding="utf-8")
    html = read("index.html")
    replacements = {
        "__VIEWER_LICENSE__": (ROOT.parent / "LICENSE").read_text(encoding="utf-8").strip(),
        "__PROJECT_JSON__": json.dumps(data, ensure_ascii=False).replace("<", "\\u003c"),
        "/*__SHELL_CSS__*/": read("shell.css"),
        "/*__PICKER_CSS__*/": read("picker.css"),
        "/*__KIT_CSS__*/": read("kit.css"),
        "/*__SCREENS_CSS__*/": Path(styles_path).read_text(encoding="utf-8") if styles_path else "",
        "/*__KIT_JS__*/": script_safe(read("kit.js")),
        "/*__SHELL_JS__*/": script_safe(read("shell.js") + "\n" + read("tour.js")),
        "/*__SCREENS_JS__*/": script_safe(Path(screens_path).read_text(encoding="utf-8")),
    }
    for marker, text in replacements.items():
        if marker not in html:
            raise ValueError(f"Marcador {marker} ausente em src/index.html. Restaure o marcador do template.")
    markers = "|".join(re.escape(marker) for marker in replacements)
    return re.sub(markers, lambda match: replacements[match.group()], html)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=ROOT / "project.json", help="Configuração JSON do projeto")
    parser.add_argument("--screens", type=Path, default=SRC / "screens/screens.js", help="JavaScript que registra as telas")
    parser.add_argument("--styles", type=Path, help="CSS adicional do protótipo")
    parser.add_argument("--output", type=Path, default=ROOT.parent / "dist/prototype-viewer.html", help="HTML de destino")
    parser.add_argument("--spec", type=Path, help="Arquivo SPEC.md opcional de rastreabilidade")
    parser.add_argument("--check", action="store_true", help="Valida e monta em memória, sem gravar arquivos")
    args = parser.parse_args(argv)
    try:
        project = load_project(args.project)
        html = build(args.project, args.screens, args.styles, project=project)
        if args.check:
            print("Configuração e arquivos válidos. Abra a prévia para conferir registro das versões e interações.")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(html, encoding="utf-8", newline="\n")
            print("built", args.output.resolve(), len(html.encode("utf-8")) // 1024, "KB")
            if args.spec:
                args.spec.parent.mkdir(parents=True, exist_ok=True)
                args.spec.write_text(render_spec_markdown(project, args.screens), encoding="utf-8", newline="\n")
                print("spec", args.spec.resolve())
    except (OSError, ValueError) as error:
        print(f"Erro ao gerar o viewer: {error}\nConfira a configuração e os caminhos informados.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
