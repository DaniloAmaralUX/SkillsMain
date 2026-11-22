import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from source_check import verify_sources


class SourceCheckTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.original = self.root / "pedido.txt"
        self.original.write_text("Resumo\nRetirar no posto escolhido.\nPrazo em aberto.", encoding="utf-8")
        self.record = {"name": "Pedido", "path": "pedido.txt", "context": [
            {"location": "linha 1", "excerpt": "Resumo", "reason": "Título"}]}
        self.rule = {"source": "Pedido", "location": "linha 2", "excerpt": "Retirar no posto escolhido."}
        self.gap = {"source": "Pedido", "location": "linha 3", "excerpt": "Prazo em aberto."}
        self.delivery = {"requirements": [{"id": "RF01", "evidence": [self.rule]}],
                         "open_questions": [{"question": "Qual prazo?", "evidence": [self.gap]}]}

    def verify(self):
        (self.root / "sources.json").write_text(json.dumps({"sources": [self.record]}), encoding="utf-8")
        verify_sources(self.root, self.delivery)

    def test_checks_named_origin_location_and_literal_text(self):
        self.verify()
        for field, value, diagnostic in [
            ("source", "Origem inventada", "não registrada"),
            ("location", "linha 999", "inexistente"),
            ("location", "linha 3", "não localizada"),
            ("excerpt", "Cobrar no posto escolhido.", "não localizada"),
        ]:
            with self.subTest(field=field, value=value):
                old = self.rule[field]
                self.rule[field] = value
                with self.assertRaisesRegex(ValueError, diagnostic):
                    self.verify()
                self.rule[field] = old
        self.original.unlink()
        with self.assertRaisesRegex(ValueError, "origem ausente"):
            self.verify()

    def test_deleted_rule_or_gap_leaves_the_original_unaccounted_for(self):
        for key in ("requirements", "open_questions"):
            with self.subTest(key=key):
                old = self.delivery.pop(key)
                self.delivery[key] = []
                with self.assertRaisesRegex(ValueError, "sem cobertura"):
                    self.verify()
                self.delivery[key] = old

    def test_private_reconciliation_allows_short_quote_only_with_matching_rule(self):
        full = self.rule["excerpt"]
        self.rule["excerpt"] = "posto escolhido"
        self.record["coverage"] = [{"target": "RF01", "location": "linha 2", "excerpt": full}]
        self.verify()
        self.record["coverage"][0]["target"] = "Qual prazo?"
        with self.assertRaisesRegex(ValueError, "sem citação"):
            self.verify()

    def test_rechecks_the_current_source_including_new_material(self):
        self.verify()
        with self.original.open("a", encoding="utf-8") as stream:
            stream.write("\nNão permitir retirada às segundas.")
        with self.assertRaisesRegex(ValueError, "sem cobertura"):
            self.verify()

    def test_rejects_false_pdf_reference_to_transcribed_text(self):
        self.record["name"] = "anexo.pdf"
        with self.assertRaisesRegex(ValueError, "extensão"):
            self.verify()

    def test_docx_paragraph_including_accents(self):
        with ZipFile(self.root / "pedido.docx", "w") as doc:
            doc.writestr("word/document.xml", '<w:document xmlns:w="urn:w"><w:body><w:p><w:r>'
                         '<w:t>Só a Rádio.</w:t></w:r></w:p></w:body></w:document>')
        self.record.update(path="pedido.docx", context=[])
        self.rule.update(location="Parágrafo 1", excerpt="Só a Rádio.")
        self.delivery["open_questions"] = []
        self.verify()
        self.rule["excerpt"] = "Só a R?dio."
        with self.assertRaisesRegex(ValueError, "não localizada"):
            self.verify()

    def test_docx_table_and_header_are_required_even_if_body_is_accounted(self):
        with ZipFile(self.root / "pedido.docx", "w") as doc:
            doc.writestr("word/document.xml", "<document><body><tbl><tr><tc><p><r><t>Estoque 10</t></r>"
                         "</p></tc></tr></tbl></body></document>")
            doc.writestr("word/header1.xml", "<hdr><p><r><t>Máximo por dia</t></r></p></hdr>")
        self.record.update(path="pedido.docx", context=[])
        self.rule.update(location="parágrafo 1", excerpt="Estoque 10")
        self.delivery["open_questions"] = []
        with self.assertRaisesRegex(ValueError, "cabeçalho 1, parágrafo 1"):
            self.verify()
        self.delivery["requirements"][0]["evidence"].append(
            {"source": "Pedido", "location": "cabeçalho 1, parágrafo 1", "excerpt": "Máximo por dia"})
        self.verify()

    def test_xlsx_reads_the_named_sheet_cells_and_multiline_range(self):
        with ZipFile(self.root / "estoque.xlsx", "w") as doc:
            doc.writestr("xl/workbook.xml", '<workbook xmlns:r="urn:rel"><sheets><sheet name="Postos" '
                         'r:id="rel1"/></sheets></workbook>')
            doc.writestr("xl/_rels/workbook.xml.rels", '<rels><rel Id="rel1" Target="worksheets/one.xml"/></rels>')
            doc.writestr("xl/worksheets/one.xml", '<worksheet><sheetData>'
                         '<row><c r="A1" t="inlineStr"><is><t>Centro</t></is></c><c r="B1"><v>2</v></c></row>'
                         '<row><c r="A2" t="inlineStr"><is><t>Praia</t></is></c><c r="B2"><v>0</v></c></row>'
                         '</sheetData></worksheet>')
        self.record.update(path="estoque.xlsx", context=[])
        self.rule.update(location="Postos!A1:B2", excerpt="Centro | 2; Praia | 0")
        self.delivery["open_questions"] = []
        self.verify()
        self.rule.update(location="Postos!B1", excerpt="0")
        with self.assertRaisesRegex(ValueError, "não localizada"):
            self.verify()

    def test_special_number_formats_and_formulas_need_review(self):
        from source_readers import cells
        for value, message in [
            ('<c r="A1"><f>2+3</f></c>', "fórmula"),
            ('<c r="A1"><f>2+3</f><v>5</v></c>', "fórmula"),
            ('<c r="A1" s="1"><v>45123</v></c>', "formato numérico"),
            ('<c r="A1" t="d"><v>2024-01-01</v></c>', "Data"),
            ('<c r="A1" t="e"><v>#N/A</v></c>', "erro"),
        ]:
            with self.subTest(value=value), ZipFile(self.root / "cell.zip", "w") as archive:
                archive.writestr("sheet.xml", "<worksheet><sheetData><row>" + value + "</row></sheetData></worksheet>")
                with self.assertRaisesRegex(ValueError, message):
                    cells(archive, "sheet.xml", [], [0, 14])


if __name__ == "__main__":
    unittest.main()
