"""Excel file scanner: classify layout, detect fields, buffer data."""

import re
import openpyxl

from ..normalize import clean_text
from .template import (
    FileTemplate, SheetTemplate, FileFormat, LayoutType,
    FieldMapping, SectionDetector, SectionDetectorKind, HeaderBlock,
)
from .synonyms import match_field_synonym


def scan_excel(path: str) -> tuple[FileTemplate, dict]:
    """Scan an Excel file. Returns (template, cell_buffers).

    cell_buffers: {sheet_name: [(row_num, text)] for single-col,
                   sheet_name: [[col_values]] for multi-col}
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    template = FileTemplate(file_format=FileFormat.EXCEL, path=path)
    cell_buffers = {}

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        sheet_tpl, cells = _scan_sheet(ws, sheet_name, template.scan_warnings)
        template.sheets.append(sheet_tpl)
        cell_buffers[sheet_name] = cells

    wb.close()
    return template, cell_buffers


def _scan_sheet(ws, sheet_name: str, warnings: list[str]) -> tuple[SheetTemplate, list]:
    """Scan a single sheet to determine its layout."""
    # Read all cells into buffer, track max columns used
    all_rows = []
    max_cols_used = 0
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=False):
        row_data = []
        last_nonempty = 0
        for idx, cell in enumerate(row):
            text = clean_text(str(cell.value)) if cell.value is not None else ""
            row_data.append(text)
            if text:
                last_nonempty = idx + 1
        all_rows.append(row_data)
        max_cols_used = max(max_cols_used, last_nonempty)

    if max_cols_used <= 1:
        return _scan_single_column(all_rows, sheet_name, warnings)
    else:
        return _scan_multi_column(all_rows, max_cols_used, sheet_name, warnings)


def _scan_single_column(rows: list, sheet_name: str, warnings: list[str]) -> tuple[SheetTemplate, list]:
    """Classify a single-column sheet."""
    # Build cell list as (row_index, text) for non-empty rows
    cells = []
    for i, row in enumerate(rows):
        text = row[0] if row else ""
        if text:
            cells.append((i, text))

    tpl = SheetTemplate(name=sheet_name, layout=LayoutType.SINGLE_COLUMN_STATEFUL, column_count=1)

    if len(cells) < 4:
        warnings.append(f"[Scanner/{sheet_name}] Trop peu de lignes ({len(cells)})")
        return tpl, cells

    # Detect header block
    header = HeaderBlock()
    header.city_row = 0

    # Row 1 (cells[1]): check for center type
    if len(cells) > 1:
        text1 = cells[1][1].lower()
        if "centre" in text1 or "compétence" in text1 or "référence" in text1:
            header.type_centre_row = 1

    # Row 2 (cells[2]): check for "Responsable :"
    if len(cells) > 2:
        if re.match(r"Responsable\s*:", cells[2][1], re.IGNORECASE):
            header.responsable_row = 2
            header.responsable_pattern = r"Responsable\s*:\s*(.*)"

    # Data start: skip address row if present
    data_start = 3
    if len(cells) > 3 and re.match(r"Adresse postale\s*:", cells[3][1], re.IGNORECASE):
        data_start = 4
    header.row_count = data_start
    tpl.header = header
    tpl.data_start_row = data_start

    # Detect section patterns in data region
    data_cells = cells[data_start:]

    has_numbered = any(re.match(r"^\d+\.?\s+", c[1]) for c in data_cells)
    if has_numbered:
        tpl.section_detectors.append(SectionDetector(
            kind=SectionDetectorKind.NUMBERED_PREFIX,
            level="specialty",
            pattern=r"^(\d+)\.?\s+(.*)",
        ))

    has_sector = any(re.match(r"Secteur\s+", c[1], re.IGNORECASE) for c in data_cells)
    if has_sector:
        tpl.section_detectors.append(SectionDetector(
            kind=SectionDetectorKind.REGEX_PATTERN,
            level="sector",
            pattern=r"^Secteur\s+(.*)",
        ))

    # Detect field label patterns by sampling data cells
    tpl.field_mappings = _detect_label_patterns(data_cells)

    # Detect multi-name and idem patterns
    all_text = " ".join(c[1] for c in data_cells)
    tpl.has_multi_names = bool(re.search(r"[A-ZÀ-Ý]{2,}\s+\w+\s*[-–/&]\s*[A-ZÀ-Ý]", all_text))
    tpl.has_idem_references = "idem" in all_text.lower()

    # City-per-sheet
    tpl.section_detectors.insert(0, SectionDetector(
        kind=SectionDetectorKind.SHEET_NAME,
        level="city",
        sheet_scope=True,
    ))

    return tpl, cells


def _scan_multi_column(rows: list, col_count: int, sheet_name: str, warnings: list[str]) -> tuple[SheetTemplate, list]:
    """Classify a multi-column (tabular) sheet."""
    tpl = SheetTemplate(name=sheet_name, layout=LayoutType.TABULAR, column_count=col_count)

    # Find header row: first row where 2+ cells match known field synonyms
    header_row_idx = None
    best_score = 0

    for i, row in enumerate(rows[:10]):
        score = 0
        for cell_text in row[:col_count]:
            if cell_text and match_field_synonym(cell_text):
                score += 1
        if score >= 2 and score > best_score:
            header_row_idx = i
            best_score = score

    if header_row_idx is not None:
        for col_idx, cell_text in enumerate(rows[header_row_idx][:col_count]):
            if not cell_text:
                continue
            field_name = match_field_synonym(cell_text)
            if field_name:
                tpl.field_mappings.append(FieldMapping(
                    doctor_field=field_name,
                    source_label=cell_text,
                    column_index=col_idx,
                ))
        tpl.data_start_row = header_row_idx + 1
    else:
        warnings.append(f"[Scanner/{sheet_name}] Tableau multi-colonnes sans en-tetes reconnus")
        tpl.layout = LayoutType.PARAGRAPH_FREETEXT

    return tpl, rows


def _detect_label_patterns(cells: list) -> list[FieldMapping]:
    """Detect which label:value patterns appear in single-column cells."""
    mappings = []
    seen = set()

    for _, text in cells[:30]:
        for field_name, synonyms in (
            ("nom", [(r"NOM\s*[–\-]\s*PRENOM", True)]),
            ("hopital", [(r"H[oô]pital\s+de\s+rattachement", True)]),
            ("adresse", [("Adresse postale", False)]),
            ("telephone", [(r"T[ée]l[ée]phone", True)]),
            ("email", [("Adresse mail", False)]),
        ):
            if field_name in seen:
                continue
            for pattern, is_regex in synonyms:
                if is_regex:
                    if re.search(pattern + r"\s*:", text, re.IGNORECASE):
                        mappings.append(FieldMapping(
                            doctor_field=field_name,
                            source_label=pattern,
                            label_regex=pattern + r"\s*:\s*",
                        ))
                        seen.add(field_name)
                        break
                else:
                    if pattern.lower() in text.lower() and ":" in text:
                        mappings.append(FieldMapping(
                            doctor_field=field_name,
                            source_label=pattern,
                            label_regex=re.escape(pattern) + r"\s*:\s*",
                        ))
                        seen.add(field_name)
                        break

    return mappings
