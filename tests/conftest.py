"""Synthetic test fixtures - programmatically generated Excel and Word files with fake data.

These fixtures replace the real resource files so the full test suite runs
without any sensitive data. All doctor names, phones, emails, and addresses
are fictional.
"""

import os
import tempfile
import shutil

import openpyxl
from docx import Document
from docx.enum.style import WD_STYLE_TYPE


_FIXTURE_DIR = None


def get_fixture_dir() -> str:
    """Return a temp directory with synthetic test files (created once per process)."""
    global _FIXTURE_DIR
    if _FIXTURE_DIR is None or not os.path.exists(_FIXTURE_DIR):
        _FIXTURE_DIR = tempfile.mkdtemp(prefix="astb_test_")
        _create_excel_fixture(_FIXTURE_DIR)
        _create_word_fixture(_FIXTURE_DIR)
        _create_annuaire_fixture(_FIXTURE_DIR)
    return _FIXTURE_DIR


def get_excel_path() -> str:
    return os.path.join(get_fixture_dir(), "test_reseau.xlsx")


def get_word_path() -> str:
    return os.path.join(get_fixture_dir(), "test_prise_en_charge.docx")


def get_annuaire_path() -> str:
    return os.path.join(get_fixture_dir(), "test_annuaire.xlsx")


def cleanup_fixtures():
    global _FIXTURE_DIR
    if _FIXTURE_DIR and os.path.exists(_FIXTURE_DIR):
        shutil.rmtree(_FIXTURE_DIR, ignore_errors=True)
        _FIXTURE_DIR = None


# ---------------------------------------------------------------------------
# Excel fixture: mimics the ASTB single-column template
# ---------------------------------------------------------------------------

def _create_excel_fixture(dest_dir: str):
    """Create a synthetic Excel file with 3 city sheets in the ASTB format."""
    wb = openpyxl.Workbook()

    # Sheet 1: Lyon (structured, 2 specialties)
    ws = wb.active
    ws.title = "Lyon"
    _write_single_col(ws, [
        "LYON",
        "Centre de reference",
        "Responsable : Pr Jean MARTIN",
        "Adresse postale : CHU Lyon\nService de Neurologie\n69000 Lyon",
        "",
        "1.   NEPHROLOGUES",
        "Secteur Pediatrie :",
        "NOM \u2013 PRENOM : BERNARD Sophie",
        "Hopital de rattachement : Hopital Femme Mere Enfant",
        "Adresse postale : 59 boulevard Pinel, 69500 Bron",
        "Telephone : 04 72 00 00 01",
        "Adresse mail : sophie.bernard@chu-lyon.test",
        "Secteur Adulte :",
        "NOM \u2013 PRENOM : Dr PETIT Marc",
        "Hopital de rattachement : Hopital Edouard Herriot",
        "Adresse postale : 5 place Arsonval, 69003 Lyon",
        "Telephone : 04 72 00 00 02",
        "Adresse mail : marc.petit@chu-lyon.test",
        "",
        "2.   DERMATOLOGUES",
        "Secteur Pediatrie :",
        "NOM \u2013 PRENOM : Dr DURAND Claire",
        "Hopital de rattachement : Hopital Femme Mere Enfant",
        "Adresse postale : 59 boulevard Pinel, 69500 Bron",
        "Telephone : 04 72 00 00 03",
        "Adresse mail :",
        "Secteur Adulte :",
        "NOM \u2013 PRENOM : idem pediatrie",
        "Hopital de rattachement :",
        "Adresse postale :",
        "Telephone :",
        "Adresse mail :",
        "",
        "3.   AUTRES SPECIALITES, pr\u00e9ciser : Neurologie pediatrique",
        "Secteur Pediatrie :",
        "NOM \u2013 PRENOM : Pr LEROY Thomas & MOREAU Julie",
        "Hopital de rattachement : Hopital Neurologique",
        "Adresse postale : 59 boulevard Pinel, 69500 Bron",
        "Telephone : 04 72 00 00 04",
        "Adresse mail : neuro.ped@chu-lyon.test",
    ])

    # Sheet 2: Strasbourg (structured, 1 specialty, some empty fields)
    ws2 = wb.create_sheet("Strasbourg")
    _write_single_col(ws2, [
        "STRASBOURG",
        "Centre de competence",
        "Responsable : Dr Marie DUBOIS",
        "Adresse postale : CHU Strasbourg\n67000 Strasbourg",
        "",
        "1.   CARDIOLOGUES",
        "Secteur Pediatrie :",
        "NOM \u2013 PRENOM : Dr ROUX Antoine",
        "Hopital de rattachement : Hopital de Hautepierre",
        "Adresse postale : avenue Moliere, 67200 Strasbourg",
        "Telephone : 0388000001",
        "Adresse mail : antoine.roux@chu-strasbourg.test",
        "Secteur Adulte :",
        "NOM \u2013 PRENOM : pas de referent",
        "Hopital de rattachement :",
        "Adresse postale :",
        "Telephone :",
        "Adresse mail :",
    ])

    # Sheet 3: Lille (free-text, like Reims)
    ws3 = wb.create_sheet("Lille")
    _write_single_col(ws3, [
        "LILLE",
        "Centre de competence",
        "Responsable : Dr Pierre LAMBERT",
        "Adresse postale : CHU Lille\n59000 Lille",
        "",
        "Dr Lambert Pierre :",
        "au CHU de Lille, neuropediatre coordinatrice du centre",
        "contact principal : neuropediatrie@chu-lille.test",
    ])

    wb.save(os.path.join(dest_dir, "test_reseau.xlsx"))
    wb.close()


def _write_single_col(ws, rows: list[str]):
    for i, text in enumerate(rows, 1):
        if text:
            ws.cell(row=i, column=1, value=text)


# ---------------------------------------------------------------------------
# Word fixture: mimics the ASTB Word document with city sections
# ---------------------------------------------------------------------------

def _create_word_fixture(dest_dir: str):
    """Create a synthetic Word doc with List Paragraph styled city headers."""
    doc = Document()

    # Ensure "List Paragraph" style exists
    styles = doc.styles
    try:
        lp_style = styles["List Paragraph"]
    except KeyError:
        lp_style = styles.add_style("List Paragraph", WD_STYLE_TYPE.PARAGRAPH)

    # City 1: Grenoble (new city, not in Excel)
    doc.add_paragraph("CHU de Grenoble", style="List Paragraph")
    doc.add_paragraph("Dr Francois GARCIA (dermatologue)")
    doc.add_paragraph("Service de dermatologie")
    doc.add_paragraph("Tel. secretariat : 04 76 00 00 01")
    doc.add_paragraph("dermatologie@chu-grenoble.test")

    # City 2: Lyon (overlaps with Excel - should merge)
    doc.add_paragraph("CHU de Lyon", style="List Paragraph")
    doc.add_paragraph("Pr Claire DURAND et Dr Nicolas FAURE")
    doc.add_paragraph("Service de dermatologie")
    doc.add_paragraph("Prise en charge enfants et adultes")
    doc.add_paragraph("Tel : 04 72 00 00 99")
    doc.add_paragraph("dermato-lyon@chu-lyon.test")

    # City 3: Clermont-Ferrand (new city)
    doc.add_paragraph("CHU de Clermont-Ferrand", style="List Paragraph")
    doc.add_paragraph("Dr Anne THOMAS, dermatologue")
    doc.add_paragraph("Tel. 04 73 00 00 01")

    doc.save(os.path.join(dest_dir, "test_prise_en_charge.docx"))


# ---------------------------------------------------------------------------
# Annuaire fixture: a pre-built structured output Excel (for enrichment tests)
# ---------------------------------------------------------------------------

def _create_annuaire_fixture(dest_dir: str):
    """Create a synthetic annuaire Excel (as if previously generated by the tool)."""
    from src.models import COLUMN_HEADERS

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Annuaire Complet"

    # Header row
    for col, header in enumerate(COLUMN_HEADERS, 1):
        ws.cell(row=1, column=col, value=header)

    # 3 existing doctors
    doctors_data = [
        ["Auvergne-Rhone-Alpes", "Lyon", "Centre de reference", "Pr Jean MARTIN",
         "NEPHROLOGIE", "", "Pediatrie", "Dr", "BERNARD", "Sophie",
         "Hopital Femme Mere Enfant", "59 boulevard Pinel, 69500 Bron",
         "04 72 00 00 01", "sophie.bernard@chu-lyon.test", "",
         "Import initial", "2025-01-15"],
        ["Auvergne-Rhone-Alpes", "Lyon", "Centre de reference", "Pr Jean MARTIN",
         "DERMATOLOGIE", "", "Pediatrie", "Dr", "DURAND", "Claire",
         "Hopital Femme Mere Enfant", "59 boulevard Pinel, 69500 Bron",
         "04 72 00 00 03", "", "",
         "Import initial", "2025-01-15"],
        ["Grand Est", "Strasbourg", "Centre de competence", "Dr Marie DUBOIS",
         "CARDIOLOGIE", "", "Pediatrie", "Dr", "ROUX", "Antoine",
         "Hopital de Hautepierre", "avenue Moliere, 67200 Strasbourg",
         "03 88 00 00 01", "antoine.roux@chu-strasbourg.test", "",
         "Import initial", "2025-01-15"],
    ]

    for row_idx, row_data in enumerate(doctors_data, 2):
        for col_idx, value in enumerate(row_data, 1):
            ws.cell(row=row_idx, column=col_idx, value=value)

    # Add summary and log sheets (minimal)
    ws2 = wb.create_sheet("Par Ville")
    ws3 = wb.create_sheet("Journal Import")

    wb.save(os.path.join(dest_dir, "test_annuaire.xlsx"))
    wb.close()
