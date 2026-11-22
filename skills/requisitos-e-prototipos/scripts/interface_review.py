"""Keep the private per-screen review bound to the exact HTML being delivered."""
import hashlib
import json
from publication import destination_file


PRINCIPLES = (
    "Raios concêntricos", "Alinhamento óptico", "Profundidade das superfícies",
    "Animações interrompíveis", "Entrada por grupos", "Saídas sutis", "Transições de ícones",
    "Suavização tipográfica", "Números tabulares", "Quebra de texto", "Contorno das imagens",
    "Resposta ao pressionar", "Primeira renderização", "Propriedades de transição",
    "Uso de will-change", "Área de toque",
)
CONDITIONAL = {"GI01", "GI02", "GI03", "GI04", "GI05", "GI06", "GI07", "GI09", "GI11", "GI12"}
IDS = tuple(f"GI{i:02d}" for i in range(1, 17))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def template(html, registry):
    screens = []
    for flow, versions in registry.items():
        for index, version in enumerate(versions, 1):
            principles = [{"id": key, "principle": title, "status": "pending", "evidence": ""}
                          for key, title in zip(IDS, PRINCIPLES)]
            screens.append({"flow": flow, "version": index, "name": version["name"],
                            "principles": principles, "browser": None})
    return {"html_sha256": sha256(html.encode("utf8")), "screens": screens}


def prepare_review(directory, expected):
    path = directory / "interface-review.json"
    state = directory / ".viewer-build"
    if path.exists():
        previous = path.read_bytes()
        try:
            if json.loads(previous).get("html_sha256") == expected["html_sha256"]:
                return path
        except (ValueError, AttributeError):
            pass
        archive = state / "reviews"
        archive.mkdir(exist_ok=True)
        (archive / f"{sha256(previous)}.json").write_bytes(previous)
    with destination_file(directory) as staged:
        staged.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        staged.replace(path)
    return path


def observations(rows, where):
    if not isinstance(rows, list):
        raise ValueError(f"Faltam os 16 princípios em {where}.")
    used = set()
    seen_observations = set()
    for row in rows:
        key = row.get("id") if isinstance(row, dict) else None
        if not isinstance(key, str) or key not in IDS or key in used:
            raise ValueError(f"Princípio desconhecido ou repetido em {where}.")
        used.add(key)
        status = row.get("status")
        if status != "passed" and not (status == "not_applicable" and key in CONDITIONAL):
            raise ValueError(f"{where} / {key} exige revisão e aprovação.")
        evidence = row.get("evidence")
        if not isinstance(evidence, str) or len(set(evidence.casefold().split())) < 4:
            raise ValueError(f"{where} / {key}: descreva o controle e o resultado observado ou justifique a condição ausente.")
        note = " ".join(evidence.casefold().split())
        if status == "passed" and note in seen_observations:
            raise ValueError(f"{where} / {key}: registre uma observação específica deste princípio.")
        if status == "passed":
            seen_observations.add(note)
    if used != set(IDS):
        raise ValueError(f"Revisão incompleta dos 16 princípios em {where}.")


def validate_review(path, expected):
    if not path.is_file():
        raise ValueError("Gere o rascunho e revise interface-review.json antes de finalizar.")
    review = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(review, dict) or review.get("html_sha256") != expected["html_sha256"]:
        raise ValueError("A revisão visual não corresponde a este HTML. Gere e revise a versão atual.")
    remaining = {(s["flow"], s["version"]) for s in expected["screens"]}
    if not isinstance(review.get("screens"), list):
        raise ValueError("A revisão deve cobrir todas as telas e versões.")
    for screen in review["screens"]:
        flow = screen.get("flow") if isinstance(screen, dict) else None
        version = screen.get("version") if isinstance(screen, dict) else None
        if not isinstance(flow, str) or type(version) is not int or (flow, version) not in remaining:
            raise ValueError("Tela/versão desconhecida ou repetida na revisão.")
        remaining.remove((flow, version))
        observations(screen.get("principles"), f"{flow} v{version}")
        validate_browser(screen.get("browser"), flow, version)
    if remaining:
        raise ValueError("Revisão visual pendente para uma ou mais telas/versões.")


def validate_browser(browser, flow, version):
    if not isinstance(browser, dict) or browser.get("flow") != flow or type(browser.get("version")) is not int or browser["version"] != version:
        raise ValueError(f"Registre a inspeção do navegador para {flow} v{version}.")
    checks = browser.get("checks")
    keys = ("transition_properties", "will_change", "hit_area")
    if not isinstance(checks, dict) or any(checks.get(k) is not True for k in keys) or browser.get("violations") != []:
        raise ValueError(f"Resolva as violações observáveis do navegador em {flow} v{version}.")
