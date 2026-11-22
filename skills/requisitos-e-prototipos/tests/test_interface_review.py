import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from interface_review import template, validate_review


class ReviewGateTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "review.json"
        registry = {"inicio": [{"name": "A"}, {"name": "B"}], "fim": [{"name": "Confirmar"}]}
        self.model = template("<html>versão exata</html>", registry)
        self.review = copy.deepcopy(self.model)
        for screen in self.review["screens"]:
            for row in screen["principles"]:
                row.update(status="passed", evidence=f"{row['principle']} conferido na apresentação sintética de teste.")
            screen["browser"] = {"flow": screen["flow"], "version": screen["version"], "violations": [],
                                 "checks": {"transition_properties": True, "will_change": True, "hit_area": True}}

    def verify(self):
        self.path.write_text(json.dumps(self.review), encoding="utf8")
        validate_review(self.path, self.model)

    def test_all_versions_and_conditional_reason_pass(self):
        self.review["screens"][1]["principles"][10].update(status="not_applicable", evidence="A tela contém somente campos de texto.")
        self.verify()

    def test_missing_extra_or_repeated_versions_fail(self):
        for change in ("missing", "extra", "repeated"):
            with self.subTest(change=change):
                screens = list(self.review["screens"])
                if change == "missing":
                    screens.pop(1)
                elif change == "extra":
                    screens.append(dict(screens[0], flow="extra"))
                else:
                    screens[1] = screens[0]
                original = self.review["screens"]
                self.review["screens"] = screens
                with self.assertRaises(ValueError):
                    self.verify()
                self.review["screens"] = original

    def test_incomplete_evidence_pending_prohibited_na_or_duplicate_principle_fail(self):
        rows = self.review["screens"][0]["principles"]
        for change in ({"status": "pending"}, {"status": "not_applicable"}, {"id": "GI15"}, {"evidence": "ok"}):
            with self.subTest(change=change):
                original = rows[-1]
                rows[-1] = dict(original, **change)
                with self.assertRaises(ValueError):
                    self.verify()
                rows[-1] = original
        rows.pop()
        with self.assertRaises(ValueError):
            self.verify()

    def test_wrong_screen_failed_measurement_or_missing_browser_fail(self):
        screen = self.review["screens"][1]
        sample = screen["browser"]
        for bad in (None, dict(sample, version=1), dict(sample, checks={}), dict(sample, violations=["alvo pequeno"]),
                    dict(sample, checks=dict(sample["checks"], hit_area=False))):
            with self.subTest(bad=bad):
                screen["browser"] = bad
                with self.assertRaises(ValueError):
                    self.verify()
