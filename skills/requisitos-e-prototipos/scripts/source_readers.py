"""Read local source text in stable, addressable units; never package the sources."""

from pathlib import PurePosixPath
import posixpath
import re
import unicodedata
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile


def normalized(text):
    return " ".join(unicodedata.normalize("NFC", text).split())


def pdf_units(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            import pymupdf
        except ImportError as error:
            raise ValueError("Para conferir PDF, instale pypdf no Python que executa o build.") from error
        with pymupdf.open(path) as document:
            return [page.get_text() for page in document]
    from pypdf.errors import PyPdfError
    try:
        return [page.extract_text() or "" for page in PdfReader(path).pages]
    except PyPdfError as error:
        raise ValueError(f"PDF ilegível: {path.name}. Verifique o arquivo original.") from error


def docx_paragraphs(archive, part):
    root = ET.fromstring(archive.read(part))
    unsupported = {"drawing", "pict", "object", "altChunk", "instrText", "fldSimple", "del", "ins"}
    if any(node.tag.split("}")[-1] in unsupported for node in root.iter()):
        raise ValueError(f"O DOCX contém figura, campo, anexo ou revisão em {part}. Confira uma cópia textual.")
    paragraphs = []
    for para in root.iterfind(".//{*}p"):
        pieces = []
        for node in para.iter():
            tag = node.tag.split("}")[-1]
            if tag == "t":
                pieces.append(node.text or "")
            elif tag in ("br", "tab"):
                pieces.append(" ")
        paragraphs.append("".join(pieces))
    return paragraphs


def docx_units(archive):
    texts = docx_paragraphs(archive, "word/document.xml")
    units = {i: normalized(text) for i, text in enumerate(texts, 1)}
    for name in archive.namelist():
        match = re.fullmatch(r"word/(header|footer)(\d+)\.xml", name)
        if match:
            label = "cabeçalho" if match[1] == "header" else "rodapé"
            for i, text in enumerate(docx_paragraphs(archive, name), 1):
                units[f"{label} {match[2]}, parágrafo {i}"] = normalized(text)
        elif name in {"word/footnotes.xml", "word/endnotes.xml", "word/comments.xml"}:
            if any(docx_paragraphs(archive, name)):
                raise ValueError(f"Material complementar em {name}. Inclua notas e comentários em cópia textual conferida.")
    return units


def rich_text(element):
    return "".join(t.text or "" for t in element.iterfind(".//{*}t"))


def cells(archive, path, strings, formats):
    root = ET.fromstring(archive.read(path))
    result = {}
    for cell in root.iterfind(".//{*}sheetData/{*}row/{*}c"):
        ref, kind = cell.attrib["r"], cell.get("t")
        value = cell.findtext("{*}v", "")
        if cell.find("{*}f") is not None:
            raise ValueError(f"A planilha contém fórmula em {ref}. Use uma cópia com valores conferidos.")
        if kind in ("d", "e") or (kind in ("n", None) and value and formats[int(cell.get("s", "0"))] != 0):
            raise ValueError(f"Data, erro ou formato numérico especial em {ref}. Confira o valor exibido em cópia textual.")
        if kind == "s":
            value = strings[int(value)]
        elif kind == "inlineStr":
            value = rich_text(cell)
        elif kind == "b":
            value = {"1": "TRUE", "0": "FALSE"}[value]
        if normalized(value):
            result[ref] = normalized(value)
    return result


def xlsx_units(archive):
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {r.get("Id"): r.get("Target") for r in relationships if r.get("TargetMode") != "External"}
    strings = []
    formats = [0]
    if any(n.startswith(("xl/charts/", "xl/drawings/", "xl/comments", "xl/pivotTables/", "xl/embeddings/"))
           for n in archive.namelist()):
        raise ValueError("Planilha com gráfico, imagem, comentário ou objeto. Registre uma cópia textual conferida.")
    if "xl/styles.xml" in archive.namelist():
        styles = ET.fromstring(archive.read("xl/styles.xml"))
        formats = [int(x.get("numFmtId", "0")) for x in styles.iterfind(".//{*}cellXfs/{*}xf")] or [0]
    if "xl/sharedStrings.xml" in archive.namelist():
        strings = [rich_text(si) for si in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("{*}si")]
    units = {}
    for sheet in workbook.iterfind(".//{*}sheets/{*}sheet"):
        name = sheet.attrib["name"]
        rel = next(value for key, value in sheet.attrib.items() if key.endswith("}id"))
        target = targets[rel]
        path = target.lstrip("/") if PurePosixPath(target).is_absolute() else posixpath.normpath("xl/" + target)
        for address, text in cells(archive, path, strings, formats).items():
            units[f"{name}!{address}"] = text
    return units


def read_source(path):
    suffix = path.suffix.lower()
    if not path.is_file():
        raise ValueError(f"Arquivo de origem ausente: {path.name}")
    try:
        if suffix == ".pdf":
            texts = pdf_units(path)
            empty = next((i for i, t in enumerate(texts, 1) if not normalized(t)), None)
            if empty:
                raise ValueError(f"Página {empty} sem texto extraível. Confira uma transcrição identificada no original.")
        elif suffix in {".docx", ".xlsx"}:
            with ZipFile(path) as archive:
                if suffix == ".xlsx":
                    return xlsx_units(archive)
                return docx_units(archive)
        elif suffix in {".txt", ".md"}:
            texts = path.read_text(encoding="utf-8-sig").splitlines()
        else:
            raise ValueError("Formato sem conferência literal. Use uma transcrição UTF-8 e registre sua revisão.")
    except (BadZipFile, ET.ParseError, KeyError, IndexError, StopIteration, RuntimeError) as exc:
        raise ValueError(f"Não foi possível interpretar {path.name}. Verifique a integridade e o formato.") from exc
    return {i: normalized(t) for i, t in enumerate(texts, 1)}


def column_number(name):
    value = 0
    for letter in name:
        value = value * 26 + ord(letter) - 64
    return value


def cell_parts(address):
    match = re.fullmatch(r"([A-Z]{1,3})([1-9]\d{0,6})", address.upper())
    if not match:
        raise ValueError(f"Endereço de célula inválido: {address}")
    x, y = column_number(match[1]), int(match[2])
    if x > 16384 or y > 1048576:
        raise ValueError(f"Célula fora dos limites da planilha: {address}")
    return x, y


def spreadsheet_range(location, units):
    sheet, separator, cells = location.rpartition("!")
    if not separator:
        raise ValueError(f"Informe aba e célula, como Postos!B2: {location}")
    sheet = sheet.removeprefix("'").removesuffix("'").replace("''", "'")
    first, _, last = cells.partition(":")
    x1, y1 = cell_parts(first)
    x2, y2 = cell_parts(last or first)
    if x1 > x2 or y1 > y2:
        raise ValueError(f"Intervalo invertido: {location}")
    selected = []
    for key in units:
        name, _, address = key.rpartition("!")
        if name == sheet:
            x, y = cell_parts(address)
            if x1 <= x <= x2 and y1 <= y <= y2:
                selected.append((y, x, key))
    selected.sort()
    return [(key, "; " if i and selected[i-1][0] != y else " | ") for i, (y, x, key) in enumerate(selected)]


def selection(suffix, location, units):
    if suffix == ".xlsx":
        return spreadsheet_range(location, units)
    if suffix == ".docx" and location.casefold() in units:
        return [(location.casefold(), " ")]
    labels = {".pdf": r"(?:p\.|páginas?|págs?\.)", ".docx": r"parágrafos?"}
    pattern = labels.get(suffix, r"linhas?")
    match = re.fullmatch(pattern + r"\s*(\d+)(?:\s*[-–]\s*(\d+))?(?:\s*[·,]\s*(.+))?", location, re.I)
    if not match:
        raise ValueError(f"Localização inválida para {suffix}: {location}")
    start, end = int(match[1]), int(match[2] or match[1])
    if start not in units or end not in units or end < start:
        raise ValueError(f"Localização inexistente na origem: {location}")
    keys = [i for i in range(start, end + 1) if units[i]]
    if match[3]:
        heading = normalized(match[3].replace("·", " ")).casefold()
        if not any(heading in units[k].casefold() for k in keys):
            raise ValueError(f"Título citado não consta da localização: {location}")
    return [(key, " ") for key in keys]
