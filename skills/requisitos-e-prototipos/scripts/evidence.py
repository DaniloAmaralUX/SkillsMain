"""Validate source references and flow coverage in a prototype delivery."""

import argparse
import json
from pathlib import Path
import sys


def text_field(item, key, path):
    if not isinstance(item, dict):
        raise ValueError(f"{path} deve ser um objeto.")
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}.{key} precisa de texto.")
    return value.strip()


def text_key(value):
    return " ".join(value.split()).casefold()


def check_references(item, path, minimum=1):
    refs = item.get("evidence")
    if not isinstance(refs, list) or len(refs) < minimum:
        raise ValueError(f"{path}.evidence exige pelo menos {minimum} referência(s).")
    distinct = set()
    for index, ref in enumerate(refs):
        label = f"{path}.evidence[{index}]"
        distinct.add(tuple(text_key(text_field(ref, k, label)) for k in ("source", "location", "excerpt")))
    if len(distinct) < minimum:
        raise ValueError(f"{path}.evidence precisa de {minimum} referências distintas.")


def check_open_questions(delivery):
    questions = delivery.get("open_questions")
    if not isinstance(questions, list):
        raise ValueError("open_questions deve ser uma lista de pendências, ou [] se não houver.")
    for index, item in enumerate(questions):
        path = f"open_questions[{index}]"
        kind = text_field(item, "kind", path)
        if kind not in ("gap", "conflict"):
            raise ValueError(f"{path}.kind deve ser gap ou conflict.")
        text_field(item, "question", path)
        check_references(item, path, minimum=2 if kind == "conflict" else 1)


def check_flow_coverage(covered, flow_ids):
    expected = set(flow_ids)
    unknown = sorted(covered - expected)
    missing = sorted(expected - covered)
    if unknown:
        raise ValueError("Requisito indica fluxo inexistente: " + ", ".join(unknown))
    if missing:
        raise ValueError("Fluxo sem requisito documentado: " + ", ".join(missing))


def validate_evidence(delivery, flow_ids=None):
    """Raise ValueError on incomplete traceability. Source interpretation is reviewed separately."""
    if not isinstance(delivery, dict):
        raise ValueError("delivery.json deve conter um objeto.")
    requirements = delivery.get("requirements")
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("requirements precisa de pelo menos um requisito com origem identificada.")
    assumptions = delivery.get("assumptions")
    if not isinstance(assumptions, list) or any(not isinstance(a, str) or not a.strip() for a in assumptions):
        raise ValueError("assumptions deve ser uma lista de textos, ou [] se não houver.")
    assumption_keys = {text_key(value) for value in assumptions}
    identifiers = set()
    covered = set()
    for index, item in enumerate(requirements):
        path = f"requirements[{index}]"
        identifier = text_field(item, "id", path)
        if identifier != item["id"]:
            raise ValueError(f"{path}.id contém espaços nas extremidades.")
        if identifier in identifiers:
            raise ValueError(f"ID de requisito duplicado: {identifier}")
        identifiers.add(identifier)
        if text_key(text_field(item, "description", path)) in assumption_keys:
            raise ValueError(f"{identifier}: a mesma afirmação aparece como hipótese e requisito.")
        flow = text_field(item, "flow", path)
        if flow != item["flow"]:
            raise ValueError(f"{path}.flow contém espaços nas extremidades.")
        covered.add(flow)
        text_field(item, "acceptance", path)
        check_references(item, path)
    check_open_questions(delivery)
    if flow_ids is not None:
        check_flow_coverage(covered, flow_ids)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("delivery", type=Path, help="Caminho de delivery.json")
    args = parser.parse_args(argv)
    try:
        delivery = json.loads(args.delivery.read_text(encoding="utf-8-sig"))
        validate_evidence(delivery)
        from source_check import verify_sources
        verify_sources(args.delivery.resolve().parent, delivery)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    print("Estrutura, citações e destinação do texto extraído conferidas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
