"""Check literal citations and account for the supplied source text before publication."""

import argparse
import json
from pathlib import Path

from source_readers import normalized, read_source, selection


class Source:
    def __init__(self, directory, entry):
        self.name = required(entry, "name")
        path = directory / required(entry, "path")
        self.suffix = path.suffix.lower()
        if Path(self.name).suffix and Path(self.name).suffix.lower() != self.suffix:
            raise ValueError(f"O nome público e a extensão da fonte divergem: {self.name}")
        self.units = read_source(path)
        if not any(self.units.values()):
            raise ValueError(f"Fonte sem texto conferível: {self.name}")
        self.covered = {key: bytearray(len(text)) for key, text in self.units.items()}
        self.citations = {}

    def locate(self, ref):
        location = required(ref, "location")
        excerpt = normalized(required(ref, "excerpt"))
        selected = selection(self.suffix, location, self.units)
        parts, offsets, pos = [], [], 0
        for key, sep in selected:
            if parts:
                parts.append(sep)
                pos += len(sep)
            text = self.units[key]
            offsets.append((key, pos, pos + len(text)))
            parts.append(text)
            pos += len(text)
        content = "".join(parts)
        start = content.find(excerpt)
        if start < 0:
            raise ValueError(f"Citação não localizada em {self.name}, {location}. Confira o trecho no original.")
        if content.find(excerpt, start + 1) >= 0:
            raise ValueError(f"Trecho ambíguo em {self.name}, {location}. Cite mais texto ou restrinja a localização.")
        end = start + len(excerpt)
        return [(k, max(a, start) - a, min(b, end) - a) for k, a, b in offsets if a < end and start < b]

    def mark(self, spans):
        for key, start, end in spans:
            self.covered[key][start:end] = b"\x01" * (end - start)

    def cite(self, target, ref):
        spans = self.locate(ref)
        self.mark(spans)
        self.citations.setdefault(target, []).extend(spans)

    def reconcile(self, entry):
        for item in entries(entry, "context"):
            required(item, "reason")
            self.mark(self.locate(item))
        for item in entries(entry, "coverage"):
            target = required(item, "target")
            spans = self.locate(item)
            cited = self.citations.get(target, ())
            if not any(k == ck and a <= ca and cb <= b for k, a, b in spans for ck, ca, cb in cited):
                raise ValueError(f"Cobertura sem citação do alvo na passagem: {self.name} / {target}")
            self.mark(spans)
        for key, text in self.units.items():
            missing = next((i for i, c in enumerate(text) if not c.isspace() and not self.covered[key][i]), None)
            if missing is not None:
                raise ValueError(f"Material sem cobertura em {self.name}, unidade {key}, caractere {missing + 1}. "
                                 "Associe a regra ou pendência e justifique separadamente o texto contextual.")


def required(obj, field):
    if not isinstance(obj, dict) or not isinstance(obj.get(field), str) or not obj[field].strip():
        raise ValueError(f"Registro de origem exige texto no campo {field}.")
    return obj[field].strip()


def entries(obj, field):
    values = obj.get(field, []) if isinstance(obj, dict) else None
    if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
        raise ValueError(f"{field} deve ser uma lista de objetos.")
    return values


def verify_sources(directory, delivery):
    manifest = directory / "sources.json"
    if not manifest.is_file():
        raise ValueError("Crie o inventário privado sources.json para conferir fontes e cobertura.")
    records = entries(json.loads(manifest.read_text(encoding="utf-8-sig")), "sources")
    if not records:
        raise ValueError("Registre cada insumo do pedido em sources.json.")
    sources = {}
    for entry in records:
        source = Source(directory, entry)
        if source.name in sources:
            raise ValueError(f"Nome de origem duplicado: {source.name}")
        sources[source.name] = source
    targets = [(i["id"], i) for i in delivery["requirements"]]
    targets.extend((i["question"], i) for i in delivery["open_questions"])
    for target, item in targets:
        for ref in item["evidence"]:
            name = ref["source"]
            if name not in sources:
                raise ValueError(f"Origem não registrada em sources.json: {name}")
            sources[name].cite(target, ref)
    for entry in records:
        sources[required(entry, "name")].reconcile(entry)


def main():
    parser = argparse.ArgumentParser(description="Inspecione as unidades do documento local para conferir as referências.")
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(read_source(args.source), ensure_ascii=True, indent=2))
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
