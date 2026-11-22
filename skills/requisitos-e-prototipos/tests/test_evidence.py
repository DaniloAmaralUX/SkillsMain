import importlib.util
from pathlib import Path
import unittest


MODULE = Path(__file__).resolve().parents[1] / "scripts/evidence.py"
spec = importlib.util.spec_from_file_location("prototype_evidence", MODULE)
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


def reference(source="Briefing.pdf", location="p. 1, Retirada", excerpt="Retirada apenas na loja escolhida."):
    return {"source": source, "location": location, "excerpt": excerpt}


def delivery():
    return {
        "requirements": [{
            "id": "RF01",
            "description": "Retirar a bicicleta na loja escolhida.",
            "flow": "retirada",
            "acceptance": "Escolher Praia e conferir que a confirmação mostra Praia.",
            "evidence": [reference()],
        }],
        "assumptions": [],
        "open_questions": [],
    }


class EvidenceTest(unittest.TestCase):
    def test_accepts_multiple_sources_and_flags_a_documented_conflict_separately(self):
        data = delivery()
        followup = reference("Chat", "Mensagem 2", "A retirada pode ocorrer em outra loja.")
        data["open_questions"].append({
            "kind": "conflict", "question": "Qual loja pode entregar a bicicleta?",
            "evidence": [reference(), followup],
        })
        data["requirements"][0].update(
            description="Escolher loja na reserva.",
            acceptance="Ao escolher uma loja, seu nome aparece na revisão.",
            evidence=[reference("Chat", "Mensagem 1", "Escolher loja na reserva.")],
        )
        evidence.validate_evidence(data, ["retirada"])

    def test_rejects_requirements_without_quoted_evidence_or_acceptance(self):
        for field in ("evidence", "acceptance"):
            with self.subTest(field=field):
                data = delivery()
                del data["requirements"][0][field]
                with self.assertRaisesRegex(ValueError, field):
                    evidence.validate_evidence(data)
        for field in ("source", "location", "excerpt"):
            with self.subTest(field=field):
                data = delivery()
                data["requirements"][0]["evidence"][0][field] = "  "
                with self.assertRaisesRegex(ValueError, field):
                    evidence.validate_evidence(data)

    def test_unrepresented_or_unknown_flows_are_reported_by_name(self):
        for flow_ids, unmatched in [(["checkout", "retirada"], "checkout"), ([], "retirada")]:
            with self.subTest(flow_ids=flow_ids), self.assertRaisesRegex(ValueError, unmatched):
                evidence.validate_evidence(delivery(), flow_ids)

    def test_uncertainty_cannot_replace_the_evidence_for_a_requirement(self):
        data = delivery()
        data["assumptions"] = ["  RETIRAR a bicicleta na loja escolhida.  "]
        with self.assertRaisesRegex(ValueError, "hipótese"):
            evidence.validate_evidence(data)

    def test_gap_requires_context_and_conflict_requires_two_distinct_references(self):
        data = delivery()
        item = {"kind": "gap", "question": "Qual o prazo de retirada?", "evidence": []}
        data["open_questions"].append(item)
        with self.assertRaisesRegex(ValueError, "evidence"):
            evidence.validate_evidence(data)
        item["evidence"] = [reference()]
        evidence.validate_evidence(data)
        item.update(kind="conflict", evidence=[reference(), reference(excerpt="Retirada apenas na   loja escolhida.")])
        with self.assertRaisesRegex(ValueError, "distintas"):
            evidence.validate_evidence(data)


if __name__ == "__main__":
    unittest.main()
