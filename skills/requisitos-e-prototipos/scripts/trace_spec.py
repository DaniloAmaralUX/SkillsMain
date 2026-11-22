"""Append source-backed requirements to the portable specification."""


def sources(item):
    return [
        f"  - {ref['source']}, {ref['location']} — “{ref['excerpt']}”"
        for ref in item["evidence"]
    ]


def trace_spec(delivery):
    lines = ["", "## Requisitos e fontes", ""]
    for item in delivery["requirements"]:
        lines.extend([
            f"### {item['id']} · {item['description']}", "",
            f"- Fluxo: {item['flow']}", f"- Aceite: {item['acceptance']}",
            "- Origem:", *sources(item), "",
        ])
    if delivery["open_questions"]:
        lines.extend(["## Questões em aberto", ""])
        for item in delivery["open_questions"]:
            kind = "Conflito" if item["kind"] == "conflict" else "Lacuna"
            lines.extend([f"- {kind}: {item['question']}", *sources(item)])
    for key, label in (("assumptions", "Decisões de apresentação"),
                       ("simulations", "Simulações"), ("limitations", "Limites")):
        if delivery[key]:
            lines.extend(["", f"## {label}", ""])
            lines.extend(f"- {text}" for text in delivery[key])
    return "\n".join(lines).rstrip() + "\n"
