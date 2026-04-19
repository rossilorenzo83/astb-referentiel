"""Generate a structured, filterable Excel output file."""

from collections import Counter
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from .models import Doctor, COLUMN_HEADERS, doctor_to_row


# Styling constants
HEADER_FILL = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
BODY_FONT = Font(name="Calibri", size=10)
NOTE_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
THIN_BORDER = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9"),
)

# Specialty display names for the summary sheet
SPECIALTIES_ORDER = [
    "NEPHROLOGIE", "PNEUMOLOGIE", "PSYCHIATRIE", "GENETIQUE",
    "OPHTALMOLOGIE", "DERMATOLOGIE", "CARDIOLOGIE", "NEUROLOGIE",
    "UROLOGIE", "AUTRE",
]


def write_excel(
    doctors: list[Doctor],
    warnings: list[str],
    output_path: str,
):
    """Write the structured Excel output file."""
    wb = Workbook()

    _write_annuaire(wb, doctors)
    _write_summary(wb, doctors)
    _write_log(wb, warnings)

    wb.save(output_path)
    wb.close()


def _write_annuaire(wb: Workbook, doctors: list[Doctor]):
    """Write the main 'Annuaire Complet' sheet."""
    ws = wb.active
    ws.title = "Annuaire Complet"

    # Header row
    for col_idx, header in enumerate(COLUMN_HEADERS, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Data rows - sort by city, then specialty, then sector
    sorted_doctors = sorted(doctors, key=lambda d: (d.ville, d.specialite, d.secteur, d.nom))

    for row_idx, doc in enumerate(sorted_doctors, 2):
        row_data = doctor_to_row(doc)
        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = BODY_FONT
            cell.border = THIN_BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)

        # Highlight rows with notes (e.g., "pas de referent")
        if doc.notes and any(kw in doc.notes.lower() for kw in ["pas de", "idem", "meme medecin"]):
            for col_idx in range(1, len(COLUMN_HEADERS) + 1):
                ws.cell(row=row_idx, column=col_idx).fill = NOTE_FILL

    # Format phone and email columns as text
    phone_col = COLUMN_HEADERS.index("Telephone") + 1
    email_col = COLUMN_HEADERS.index("Email") + 1
    for row_idx in range(2, len(sorted_doctors) + 2):
        ws.cell(row=row_idx, column=phone_col).number_format = "@"
        ws.cell(row=row_idx, column=email_col).number_format = "@"

    # Auto-fit column widths
    _auto_fit_columns(ws, len(sorted_doctors) + 1)

    # Freeze header row
    ws.freeze_panes = "A2"

    # AutoFilter
    if sorted_doctors:
        last_col = get_column_letter(len(COLUMN_HEADERS))
        ws.auto_filter.ref = f"A1:{last_col}{len(sorted_doctors) + 1}"


def _write_summary(wb: Workbook, doctors: list[Doctor]):
    """Write the 'Par Ville' summary sheet."""
    ws = wb.create_sheet("Par Ville")

    # Collect cities and counts
    cities = sorted(set(d.ville for d in doctors))
    specialties_present = sorted(set(d.specialite for d in doctors if d.specialite),
                                  key=lambda s: SPECIALTIES_ORDER.index(s) if s in SPECIALTIES_ORDER else 99)

    # Header row
    headers = ["Ville", "Total"] + specialties_present
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")

    # Data
    counts = Counter((d.ville, d.specialite) for d in doctors if d.nom)
    city_totals = Counter(d.ville for d in doctors if d.nom)

    for row_idx, city in enumerate(cities, 2):
        ws.cell(row=row_idx, column=1, value=city).font = Font(name="Calibri", size=10, bold=True)
        ws.cell(row=row_idx, column=2, value=city_totals[city]).font = BODY_FONT

        for col_idx, spec in enumerate(specialties_present, 3):
            count = counts.get((city, spec), 0)
            cell = ws.cell(row=row_idx, column=col_idx, value=count if count else "")
            cell.font = BODY_FONT
            cell.alignment = Alignment(horizontal="center")

    # Total row
    total_row = len(cities) + 2
    ws.cell(row=total_row, column=1, value="TOTAL").font = Font(name="Calibri", size=10, bold=True)
    ws.cell(row=total_row, column=2, value=sum(city_totals.values())).font = Font(name="Calibri", size=10, bold=True)
    for col_idx, spec in enumerate(specialties_present, 3):
        total = sum(counts.get((city, spec), 0) for city in cities)
        ws.cell(row=total_row, column=col_idx, value=total).font = Font(name="Calibri", size=10, bold=True)

    _auto_fit_columns(ws, total_row)
    ws.freeze_panes = "B2"


def _write_log(wb: Workbook, warnings: list[str]):
    """Write the 'Journal Import' log sheet."""
    ws = wb.create_sheet("Journal Import")

    ws.cell(row=1, column=1, value="Message").font = HEADER_FONT
    ws.cell(row=1, column=1).fill = HEADER_FILL

    if warnings:
        for row_idx, warning in enumerate(warnings, 2):
            ws.cell(row=row_idx, column=1, value=warning).font = BODY_FONT
    else:
        ws.cell(row=2, column=1, value="Aucun avertissement").font = BODY_FONT

    ws.column_dimensions["A"].width = 100


def _auto_fit_columns(ws, max_row: int):
    """Auto-fit column widths based on content, with min/max bounds."""
    for col_idx in range(1, ws.max_column + 1):
        max_length = 0
        col_letter = get_column_letter(col_idx)

        for row_idx in range(1, min(max_row + 1, 50)):  # sample first 50 rows
            cell = ws.cell(row=row_idx, column=col_idx)
            if cell.value:
                # Count length, accounting for line breaks
                lines = str(cell.value).split("\n")
                length = max(len(line) for line in lines)
                max_length = max(max_length, length)

        # Clamp between 8 and 40
        width = min(max(max_length + 2, 8), 40)
        ws.column_dimensions[col_letter].width = width
