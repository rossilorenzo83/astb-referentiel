"""Template-driven parser: handles all layout types natively."""

import re
import copy

from ..models import Doctor, SPECIALTY_MAP, get_region
from ..normalize import (
    clean_text, normalize_phone, normalize_name, split_multiple_names,
    split_at_field_labels,
)
from .template import (
    FileTemplate, SheetTemplate, FileFormat, LayoutType,
    SectionDetectorKind,
)
from .synonyms import match_specialty, SPECIALTY_PREFIXES

# City name normalization
_VILLE_MAP = {
    "PARIS ROBERT DEBRE": "Paris Robert Debre",
    "PARIS ROBERT DEBRÉ": "Paris Robert Debre",
    "SAINT ETIENNE": "Saint-Etienne",
    "SAINT-ETIENNE": "Saint-Etienne",
}

# Word city header -> normalized city name
_WORD_CITY_MAP = {
    "Centre Hospitalier Annecy Genevois": "Annecy",
    "CHU de Nantes": "Nantes",
    "CHU de Montpellier": "Montpellier",
    "CHU de Toulouse": "Toulouse",
    "CHU de Marseille": "Marseille",
    "Hôpital Saint-Louis": "Paris",
    "CHU d\u2019Angers": "Angers",
    "CHU d'Angers": "Angers",
    "CHU de Bordeaux": "Bordeaux",
    "CHU de Nice (Hôpital Archet 2)": "Nice",
    "CHU de Nice": "Nice",
    "CHRU de Nancy": "Nancy",
    "CHU de Rouen": "Rouen",
    "CHU de la Réunion": "La Reunion",
    "CHU de Dijon": "Dijon",
    "Hôpital Avicenne, Bobigny": "Bobigny",
    "Hôpital Avicenne": "Bobigny",
    "CHU Brest": "Brest",
}


def parse_with_template(
    template: FileTemplate,
    buffer: dict,
) -> tuple[list[Doctor], list[str]]:
    """Parse file data using a pre-scanned template."""
    all_doctors = []
    warnings = list(template.scan_warnings)

    for sheet_tpl in template.sheets:
        if sheet_tpl.layout == LayoutType.TABULAR:
            docs, warns = _parse_tabular(sheet_tpl, buffer, template)
        elif sheet_tpl.layout == LayoutType.SINGLE_COLUMN_STATEFUL:
            docs, warns = _parse_single_column(sheet_tpl, buffer, template)
        elif sheet_tpl.layout == LayoutType.PARAGRAPH_SECTIONED:
            docs, warns = _parse_paragraph_sectioned(sheet_tpl, buffer, template)
        elif sheet_tpl.layout == LayoutType.PARAGRAPH_FREETEXT:
            docs, warns = _parse_freetext(sheet_tpl, buffer, template)
        else:
            docs, warns = [], [f"[{sheet_tpl.name}] Layout non supporte"]

        all_doctors.extend(docs)
        warnings.extend(warns)

    return all_doctors, warnings


# ---------------------------------------------------------------------------
# TABULAR layout
# ---------------------------------------------------------------------------

def _parse_tabular(sheet: SheetTemplate, buffer: dict, file_tpl: FileTemplate) -> tuple[list[Doctor], list[str]]:
    warnings = []
    doctors = []

    col_to_field = {fm.column_index: fm.doctor_field for fm in sheet.field_mappings if fm.column_index is not None}
    if not col_to_field:
        return [], [f"[{sheet.name}] Aucun mapping de colonnes"]

    source = file_tpl.file_format.name.capitalize()

    if file_tpl.file_format == FileFormat.EXCEL:
        rows = buffer.get(sheet.name, [])
        data_rows = rows[sheet.data_start_row:]
    else:
        tables = buffer.get("tables", [])
        data_rows = []
        for table in tables:
            data_rows.extend(table[1:])

    for row_data in data_rows:
        if isinstance(row_data, tuple) and len(row_data) == 2:
            _, values = row_data
            if isinstance(values, str):
                values = [values]
        else:
            values = row_data

        if not any(v for v in values if isinstance(v, str) and v.strip()):
            continue

        doc = Doctor(source=source)
        for col_idx, field_name in col_to_field.items():
            if col_idx < len(values):
                value = clean_text(str(values[col_idx])) if values[col_idx] else ""
                if value:
                    _set_doctor_field(doc, field_name, value)

        if doc.ville:
            doc.region = get_region(doc.ville)

        if not doc.is_empty():
            doctors.append(doc)

    return doctors, warnings


# ---------------------------------------------------------------------------
# SINGLE_COLUMN_STATEFUL layout (full state machine)
# ---------------------------------------------------------------------------

def _parse_single_column(sheet: SheetTemplate, buffer: dict, file_tpl: FileTemplate) -> tuple[list[Doctor], list[str]]:
    """State machine parser for single-column sheets, driven by template."""
    warnings = []
    cells = buffer.get(sheet.name, [])

    if len(cells) < 4:
        warnings.append(f"[{sheet.name}] Trop peu de lignes ({len(cells)})")
        return [], warnings

    # --- Extract header ---
    ville = _normalize_ville(cells[0][1] if isinstance(cells[0], tuple) else cells[0])
    type_centre = cells[1][1] if isinstance(cells[1], tuple) else cells[1]

    responsable = ""
    if sheet.header and sheet.header.responsable_row is not None:
        resp_idx = sheet.header.responsable_row
        resp_text = cells[resp_idx][1] if isinstance(cells[resp_idx], tuple) else cells[resp_idx]
        if sheet.header.responsable_pattern:
            m = re.match(sheet.header.responsable_pattern, resp_text, re.IGNORECASE)
            responsable = m.group(1).strip() if m else resp_text
        else:
            responsable = resp_text

    region = get_region(ville)

    # Check if this sheet has numbered specialty sections
    has_spec_detector = any(
        d.kind == SectionDetectorKind.NUMBERED_PREFIX for d in sheet.section_detectors
    )

    # If no numbered sections detected, treat as freetext within this sheet
    if not has_spec_detector:
        return _parse_freetext_single_col(cells, ville, type_centre, responsable, region, sheet, warnings)

    # --- State machine ---
    doctors_raw = []
    current_specialty = ""
    current_specialty_detail = ""
    current_sector = ""
    current_doctor = None

    def finalize_doctor():
        nonlocal current_doctor
        if current_doctor and (current_doctor.nom or current_doctor.notes
                               or hasattr(current_doctor, "_raw_name")):
            doctors_raw.append(current_doctor)
        current_doctor = None

    def new_doctor() -> Doctor:
        return Doctor(
            region=region, ville=ville, type_centre=type_centre,
            responsable_centre=responsable, specialite=current_specialty,
            specialite_detail=current_specialty_detail, secteur=current_sector,
            source="Excel",
        )

    start_idx = sheet.data_start_row

    for idx in range(start_idx, len(cells)):
        cell = cells[idx]
        text = cell[1] if isinstance(cell, tuple) else cell

        # --- Specialty header ---
        spec_match = re.match(r"^(\d+)\.?\s+(.*)", text)
        if spec_match:
            finalize_doctor()
            spec_text = spec_match.group(2).strip()

            # Inline sector on same line
            inline_sector = None
            sector_in_spec = re.search(r"\s+Secteur\s+(.*)", spec_text, re.IGNORECASE)
            if sector_in_spec:
                spec_text = spec_text[:sector_in_spec.start()].strip()
                inline_sector = _parse_sector_value(sector_in_spec.group(1))

            # Detail after comma/colon
            detail = ""
            for sep in [", préciser :", ", préciser:", ":"]:
                if sep in spec_text:
                    parts = spec_text.split(sep, 1)
                    spec_text = parts[0].strip()
                    detail = parts[1].strip()
                    break

            spec_upper = spec_text.upper().strip().rstrip(":")
            current_specialty = SPECIALTY_MAP.get(spec_upper, spec_upper)
            current_specialty_detail = detail

            # If classified as AUTRE but detail contains a known specialty,
            # reclassify (e.g., "AUTRES SPECIALITES, préciser : Neurologie" → NEUROLOGIE)
            if current_specialty == "AUTRE" and detail:
                resolved = match_specialty(detail)
                if resolved:
                    current_specialty = resolved

            if inline_sector:
                current_sector = inline_sector
            continue

        # --- Split cell at field labels ---
        fields = split_at_field_labels(text)

        for label, value in fields:
            value = value.strip()

            if label == "secteur" or (label in ("prefix", "raw") and _is_sector_line(value)):
                finalize_doctor()
                sector_text = value
                if label in ("prefix", "raw"):
                    sm = re.match(r"Secteur\s+(.*)", sector_text, re.IGNORECASE)
                    if sm:
                        sector_text = sm.group(1)
                current_sector = _parse_sector_value(sector_text)

            elif label == "nom":
                finalize_doctor()
                current_doctor = new_doctor()
                raw_name = value.strip()
                if not raw_name:
                    current_doctor = None
                    continue

                lower = raw_name.lower()
                if any(kw in lower for kw in ["idem", "pas de référent", "pas de referent",
                                               "pas de correspondant"]):
                    current_doctor.notes = raw_name
                    if "ou " in raw_name and not lower.startswith("pas "):
                        name_part = raw_name.split(" ou ")[0].strip()
                        titre, nom, prenom = normalize_name(name_part)
                        current_doctor.titre = titre
                        current_doctor.nom = nom
                        current_doctor.prenom = prenom
                else:
                    current_doctor._raw_name = raw_name
                    if " ou " in raw_name:
                        parts = raw_name.split(" ou ", 1)
                        current_doctor._raw_name = parts[0].strip()
                        current_doctor.notes = f"ou {parts[1].strip()}"

            elif label == "hopital":
                if current_doctor:
                    current_doctor.hopital = value

            elif label == "adresse":
                if current_doctor:
                    current_doctor.adresse = value.lstrip(":").strip()

            elif label == "telephone":
                if current_doctor:
                    current_doctor.telephone = normalize_phone(value)

            elif label == "email":
                if current_doctor:
                    email = re.sub(r"\(.*?\)", "", value).strip()
                    email = re.sub(r"^\s*:?\s*", "", email)
                    current_doctor.email = email

            elif label in ("raw", "prefix"):
                if current_doctor and value and value != ":":
                    if current_doctor.notes:
                        current_doctor.notes += " ; " + value
                    else:
                        current_doctor.notes = value

    finalize_doctor()

    # --- Post-processing ---
    if sheet.has_multi_names:
        doctors_raw = _expand_multi_names(doctors_raw)
    else:
        # Always try expand - scanner detection is heuristic
        doctors_raw = _expand_multi_names(doctors_raw)

    if sheet.has_idem_references:
        doctors_raw = _resolve_idem(doctors_raw, warnings, sheet.name)
    else:
        doctors_raw = _resolve_idem(doctors_raw, warnings, sheet.name)

    doctors = [d for d in doctors_raw if not d.is_empty()]
    return doctors, warnings


def _parse_freetext_single_col(cells, ville, type_centre, responsable, region, sheet, warnings):
    """Parse a single-column sheet with no numbered structure."""
    full_text = " ".join(
        (c[1] if isinstance(c, tuple) else c) for c in cells[4:]
    )
    doctors = []

    doc = Doctor(
        region=region, ville=ville, type_centre=type_centre,
        responsable_centre=responsable, source="Excel",
    )

    # Try to find a doctor name
    name_match = re.search(r"(Dr|Pr)\s+(\w[\w\-]+)\s+(\w[\w\-]+)",
                           (cells[4][1] if isinstance(cells[4], tuple) else cells[4]) if len(cells) > 4 else "")
    if name_match:
        doc.titre = "Pr" if name_match.group(1).lower().startswith("pr") else "Dr"
        doc.nom = name_match.group(2).upper()
        doc.prenom = name_match.group(3)

    email_match = re.search(r"[\w\.\-]+@[\w\.\-]+\.\w+", full_text)
    if email_match:
        doc.email = email_match.group(0)

    # Detect specialty from text
    spec = None
    for word in full_text.lower().split():
        spec = match_specialty(word)
        if spec:
            break
    doc.specialite = spec or ""

    # Detect sector - for freetext, if a specific role title like "neuropédiatre"
    # or "pédiatre" is found, default to Pediatrie (that's the doctor's primary role
    # even if "adulte" is mentioned in context of transitions/referrals)
    lower_text = full_text.lower()
    if re.search(r"(?:neuro)?p[ée]diatre", lower_text):
        doc.secteur = "Pediatrie"
    else:
        doc.secteur = _detect_sector(full_text)
    doc.notes = full_text[:500]

    if doc.nom:
        doctors.append(doc)
    else:
        warnings.append(f"[{sheet.name}] Feuille en texte libre, aucun medecin extrait")

    return doctors, warnings


# ---------------------------------------------------------------------------
# PARAGRAPH_SECTIONED layout (full implementation)
# ---------------------------------------------------------------------------

def _parse_paragraph_sectioned(sheet: SheetTemplate, buffer: dict, file_tpl: FileTemplate) -> tuple[list[Doctor], list[str]]:
    """Parse paragraph-based documents with styled section headers."""
    warnings = []
    doctors = []
    paragraphs = buffer.get("paragraphs", [])

    # Find the city-level section detector
    city_detector = next((d for d in sheet.section_detectors if d.level == "city"), None)
    if not city_detector:
        # No section structure - fall through to freetext
        return _parse_freetext(sheet, buffer, file_tpl)

    current_city = ""
    current_block = []

    def finalize_block():
        if current_city and current_block:
            block_docs = _parse_word_city_block(current_city, current_block, warnings)
            doctors.extend(block_docs)

    for style, text in paragraphs:
        if not text:
            continue

        is_header = False
        if city_detector.kind == SectionDetectorKind.STYLE_BASED:
            is_header = (style == city_detector.pattern)
        elif city_detector.kind == SectionDetectorKind.BOLD_OR_HEADING:
            is_header = style.startswith("Heading")

        if is_header:
            finalize_block()
            current_city = _resolve_word_city(text)
            current_block = []
        else:
            current_block.append(text)

    finalize_block()
    return doctors, warnings


def _parse_word_city_block(city: str, paragraphs: list[str], warnings: list[str]) -> list[Doctor]:
    """Parse a city block from a Word document into Doctor records."""
    doctors = []
    full_text = " ".join(paragraphs)

    # Detect specialties
    specialties = set()
    for prefix, spec in SPECIALTY_PREFIXES.items():
        if prefix in full_text.lower():
            specialties.add(spec)

    primary_specialty = ""
    if specialties:
        if "DERMATOLOGIE" in specialties:
            primary_specialty = "DERMATOLOGIE"
        else:
            primary_specialty = sorted(specialties)[0]

    sector = _detect_sector(full_text)

    # Extract doctor names
    name_pattern = re.compile(
        r"(Dr|Pr|Professeur)\s+([\w\-À-ÿ]+(?:\s+[\w\-À-ÿ]+){0,3}?)(?=\s*[\(,;:\n]|\s+(?:et|&)\s|\s+(?:Service|Prise|Consultation|Tél|tél|Centre|prise|suivi|Suivi|de\s+(?:dermato|neuro|pneumo|géné|néphro))|\s*$)",
        re.IGNORECASE
    )

    referent_pattern = re.compile(
        r"(?:Référent|Référente|référent)\w*\s+(?:en\s+)?(?:\w+\s+)*?:\s*(Dr|Pr)?\s*([\w\-À-ÿ]+(?:\s+[\w\-À-ÿ]+)*)",
        re.IGNORECASE
    )

    # Extract phones
    phones = []
    for pm in re.finditer(r"(?:Tél\.?\s*(?:secrétariat\s*)?:?\s*|tél\s*:?\s*)([\d\s\.]+)", full_text, re.IGNORECASE):
        phone = normalize_phone(pm.group(1))
        if phone:
            phones.append(phone)
    for pm in re.finditer(r"\b(0[\d\s\.]{9,14})\b", full_text):
        phone = normalize_phone(pm.group(1))
        if phone and phone not in phones:
            phones.append(phone)

    # Extract emails
    emails = re.findall(r"[\w\.\-]+@[\w\.\-]+\.\w+", full_text)

    # Find names
    found_names = []
    for match in name_pattern.finditer(full_text):
        title_raw = match.group(1)
        name_raw = match.group(2).strip()
        if name_raw.lower() in ("dr", "pr", "de", "du", "la", "le", "les", "des", "en"):
            continue
        found_names.append((title_raw, name_raw))

    if not found_names:
        for match in referent_pattern.finditer(full_text):
            title_raw = match.group(1) or ""
            name_raw = match.group(2).strip()
            if name_raw and name_raw.lower() not in ("de", "du", "la"):
                found_names.append((title_raw, name_raw))

    if not found_names:
        for match in re.finditer(r"\b([A-ZÀ-Ö]{2,})\s+([A-Za-zÀ-ÿ\-]+)\b", full_text):
            found_names.append(("", f"{match.group(1)} {match.group(2)}"))

    for title_raw, name_raw in found_names:
        titre = ""
        if title_raw:
            titre = "Pr" if title_raw.lower().startswith("pr") else "Dr"

        _, nom, prenom = normalize_name(name_raw)
        # Word doc uses Firstname Lastname order - fix when all titlecase
        words = name_raw.split()
        all_titlecase = all(
            not (w.replace("-", "") == w.replace("-", "").upper() and w[0].isalpha())
            for w in words if w.replace("-", "")
        )
        if all_titlecase and len(words) >= 2:
            nom = words[-1].upper()
            prenom = " ".join(words[:-1])

        doc = Doctor(
            region=get_region(city), ville=city,
            specialite=primary_specialty, secteur=sector,
            titre=titre, nom=nom, prenom=prenom,
            telephone=phones[0] if phones else "",
            email=emails[0] if emails else "",
            source="Word",
        )
        if len(phones) > 1:
            doc.telephone = " / ".join(phones)
        if len(emails) > 1:
            doc.email = " ; ".join(emails)

        doctors.append(doc)

    if not doctors:
        warnings.append(f"[Word] Aucun medecin extrait pour {city}")

    return doctors


# ---------------------------------------------------------------------------
# PARAGRAPH_FREETEXT layout
# ---------------------------------------------------------------------------

def _parse_freetext(sheet: SheetTemplate, buffer: dict, file_tpl: FileTemplate) -> tuple[list[Doctor], list[str]]:
    warnings = []
    doctors = []

    if file_tpl.file_format == FileFormat.WORD:
        paragraphs = buffer.get("paragraphs", [])
        all_text = " ".join(t for _, t in paragraphs if t)
    else:
        cells = buffer.get(sheet.name, [])
        if isinstance(cells, list) and cells:
            if isinstance(cells[0], tuple):
                all_text = " ".join(c[1] for c in cells)
            else:
                all_text = " ".join(str(row[0]) if row else "" for row in cells)
        else:
            all_text = ""

    if not all_text.strip():
        return [], [f"[{sheet.name}] Aucun texte a analyser"]

    # Detect city
    city = ""
    from ..models import CITY_TO_REGION
    for city_name in CITY_TO_REGION:
        if city_name.lower() in all_text.lower():
            city = city_name.title()
            break

    # Detect specialty
    specialite = ""
    for word in all_text.lower().split():
        spec = match_specialty(word)
        if spec:
            specialite = spec
            break

    # Extract names
    name_pattern = re.compile(
        r"(Dr|Pr|Professeur)\s+([\w\-À-ÿ]+(?:\s+[\w\-À-ÿ]+){0,3}?)(?=\s*[\(,;:\n]|\s+(?:et|&)\s|\s+(?:Service|Prise|Consultation|Tél)|\s*$)",
        re.IGNORECASE
    )

    phones = _extract_phones(all_text)
    emails = re.findall(r"[\w\.\-]+@[\w\.\-]+\.\w+", all_text)

    for match in name_pattern.finditer(all_text):
        title_raw = match.group(1)
        name_raw = match.group(2).strip()
        if name_raw.lower() in ("dr", "pr", "de", "du", "la", "le"):
            continue

        titre = "Pr" if title_raw.lower().startswith("pr") else "Dr"
        _, nom, prenom = normalize_name(name_raw)

        words = name_raw.split()
        all_titlecase = all(
            not (w.replace("-", "") == w.replace("-", "").upper() and w[0].isalpha())
            for w in words if w.replace("-", "")
        )
        if all_titlecase and len(words) >= 2:
            nom = words[-1].upper()
            prenom = " ".join(words[:-1])

        doc = Doctor(
            region=get_region(city), ville=city,
            specialite=specialite, titre=titre,
            nom=nom, prenom=prenom,
            telephone=phones[0] if phones else "",
            email=emails[0] if emails else "",
            source=file_tpl.file_format.name.capitalize(),
        )
        doctors.append(doc)

    if not doctors:
        warnings.append(f"[{sheet.name}] Aucun medecin extrait du texte libre")

    return doctors, warnings


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _set_doctor_field(doc: Doctor, field_name: str, value: str):
    if field_name == "nom":
        titre, nom, prenom = normalize_name(value)
        doc.titre = titre or doc.titre
        doc.nom = nom
        doc.prenom = prenom
    elif field_name == "prenom":
        doc.prenom = value
    elif field_name == "telephone":
        doc.telephone = normalize_phone(value)
    elif field_name == "email":
        doc.email = re.sub(r"\(.*?\)", "", value).strip()
    elif field_name == "specialite":
        spec = match_specialty(value)
        doc.specialite = spec if spec else value.upper()
    elif field_name == "ville":
        doc.ville = value
        doc.region = get_region(value)
    elif hasattr(doc, field_name):
        setattr(doc, field_name, value)


def _normalize_ville(raw: str) -> str:
    raw = clean_text(raw)
    upper = raw.upper()
    if upper in _VILLE_MAP:
        return _VILLE_MAP[upper]
    return raw.title()


def _is_sector_line(text: str) -> bool:
    return bool(re.match(r"Secteur\s+", text, re.IGNORECASE))


def _parse_sector_value(text: str) -> str:
    text = text.strip().rstrip(":").strip()
    lower = text.lower()
    if "adulte" in lower and ("péd" in lower or "ped" in lower or "enfant" in lower):
        return "Pediatrie et Adulte"
    if "péd" in lower or "ped" in lower or "enfant" in lower or "ado" in lower:
        return "Pediatrie"
    if "adulte" in lower:
        return "Adulte"
    for kw in ["Pédiatrie", "Pediatrie", "pédiatrie"]:
        if kw in text:
            return "Pediatrie"
    for kw in ["Adulte", "adulte"]:
        if kw in text:
            return "Adulte"
    return text if text else "Non precise"


def _detect_sector(text: str) -> str:
    lower = text.lower()
    has_enfant = "enfant" in lower or "pédiat" in lower or "pediatr" in lower
    has_adulte = "adulte" in lower
    if has_enfant and has_adulte:
        return "Pediatrie et Adulte"
    if has_enfant:
        return "Pediatrie"
    if has_adulte:
        return "Adulte"
    return ""


def _resolve_word_city(header_text: str) -> str:
    header_text = header_text.strip()
    for pattern, city in _WORD_CITY_MAP.items():
        if pattern.lower() in header_text.lower():
            return city
    city = re.sub(
        r"^(?:CHU\s+(?:d[e']\s*)?|CHRU\s+(?:de\s+)?|Centre\s+Hospitalier\s+(?:de\s+)?|Hôpital\s+)",
        "", header_text, flags=re.IGNORECASE
    )
    return city.strip().lstrip("'").strip()


def _extract_phones(text: str) -> list[str]:
    phones = []
    for m in re.finditer(r"(?:\+33\s*[\s\.\-]?\s*|0)[\d\s\.\-]{8,}", text):
        phone = normalize_phone(m.group())
        if phone and phone not in phones:
            phones.append(phone)
    return phones


def _expand_multi_names(doctors_raw: list[Doctor]) -> list[Doctor]:
    expanded = []
    for doc in doctors_raw:
        raw_name = getattr(doc, "_raw_name", None)
        if raw_name:
            names = split_multiple_names(raw_name)
            for name in names:
                new_doc = copy.deepcopy(doc)
                titre, nom, prenom = normalize_name(name)
                new_doc.titre = titre
                new_doc.nom = nom
                new_doc.prenom = prenom
                if hasattr(new_doc, "_raw_name"):
                    del new_doc._raw_name
                expanded.append(new_doc)
        else:
            if hasattr(doc, "_raw_name"):
                del doc._raw_name
            expanded.append(doc)
    return expanded


def _resolve_idem(doctors: list[Doctor], warnings: list[str], sheet_name: str) -> list[Doctor]:
    ped_lookup = {}
    for doc in doctors:
        if doc.secteur == "Pediatrie" and doc.nom:
            key = doc.specialite
            if key not in ped_lookup:
                ped_lookup[key] = doc

    for doc in doctors:
        if doc.notes and "idem" in doc.notes.lower() and not doc.nom:
            ref = ped_lookup.get(doc.specialite)
            if ref:
                doc.nom = ref.nom
                doc.prenom = ref.prenom
                doc.titre = ref.titre
                doc.hopital = doc.hopital or ref.hopital
                doc.adresse = doc.adresse or ref.adresse
                doc.telephone = doc.telephone or ref.telephone
                doc.email = doc.email or ref.email
                doc.notes = "Meme medecin que secteur Pediatrie"
            else:
                warnings.append(
                    f"[{sheet_name}] Reference 'idem pediatrie' pour {doc.specialite} "
                    f"mais aucun medecin pediatrie trouve"
                )
    return doctors
