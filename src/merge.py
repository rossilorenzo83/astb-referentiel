"""Merge, deduplication, and enrichment logic for doctor records."""

from datetime import date

from .models import Doctor, get_region
from .normalize import strip_accents, edit_distance


def merge_all(doctors_list: list[Doctor]) -> tuple[list[Doctor], list[str]]:
    """Deduplicate a flat list of doctors from any number of sources.

    Returns (deduplicated_list, conflict_warnings).
    """
    warnings = []
    merged = []

    for doc in doctors_list:
        if not doc.nom:
            merged.append(doc)
            continue

        match = find_match(doc, merged)
        if match:
            merge_into(match, doc, warnings)
        else:
            merged.append(doc)

    return merged, warnings


def enrich(
    existing: list[Doctor],
    new_doctors: list[Doctor],
) -> tuple[list[Doctor], list[str]]:
    """Enrich an existing annuaire with new doctor records.

    - Same-city match: update/supplement existing record
    - Cross-city match (transfer): update city/hospital/address, log transfer
    - No match: add as new entry
    - Never deletes existing records

    Returns (enriched_list, warnings).
    """
    warnings = []
    result = list(existing)  # preserve all existing records

    for new_doc in new_doctors:
        if not new_doc.nom:
            continue

        # First try same-city match
        same_city = find_match(new_doc, result, cross_city=False)
        if same_city:
            _enrich_merge(same_city, new_doc, warnings)
            continue

        # Then try cross-city match (transfer detection)
        cross_city = find_match(new_doc, result, cross_city=True)
        if cross_city:
            _handle_transfer(cross_city, new_doc, warnings)
            continue

        # No match: add as new entry
        result.append(new_doc)
        warnings.append(
            f"Nouveau medecin ajoute : {new_doc.titre} {new_doc.nom} {new_doc.prenom} "
            f"({new_doc.ville}, {new_doc.specialite})"
        )

    return result, warnings


def _enrich_merge(target: Doctor, source: Doctor, warnings: list[str]):
    """Merge new data into an existing record (same city)."""
    conflicts = []

    for field in ["hopital", "adresse", "telephone", "email"]:
        target_val = getattr(target, field)
        source_val = getattr(source, field)

        if source_val and not target_val:
            setattr(target, field, source_val)
        elif source_val and target_val and source_val != target_val:
            conflicts.append(f"{field}: '{target_val}' -> '{source_val}'")
            # Update to new value (newer data takes precedence in enrichment)
            setattr(target, field, source_val)

    # Supplement empty metadata fields
    for field in ["titre", "prenom", "specialite", "specialite_detail",
                   "secteur", "type_centre", "responsable_centre"]:
        if getattr(source, field) and not getattr(target, field):
            setattr(target, field, getattr(source, field))

    # Update source and date
    _append_source(target, source.source)
    target.date_import = date.today().isoformat()

    if conflicts:
        warnings.append(
            f"Mise a jour {target.nom} {target.prenom} ({target.ville}): "
            + "; ".join(conflicts)
        )


def _handle_transfer(target: Doctor, source: Doctor, warnings: list[str]):
    """Handle a doctor transfer (same name+specialty, different city)."""
    old_city = target.ville
    old_hopital = target.hopital

    # Update location fields from the new source
    target.ville = source.ville
    target.region = get_region(source.ville)
    if source.hopital:
        target.hopital = source.hopital
    if source.adresse:
        target.adresse = source.adresse
    if source.telephone:
        target.telephone = source.telephone
    if source.email:
        target.email = source.email
    if source.type_centre:
        target.type_centre = source.type_centre
    if source.responsable_centre:
        target.responsable_centre = source.responsable_centre

    # Supplement empty fields
    for field in ["titre", "prenom", "specialite", "specialite_detail", "secteur"]:
        if getattr(source, field) and not getattr(target, field):
            setattr(target, field, getattr(source, field))

    # Record the transfer
    transfer_note = f"Transfere de {old_city}"
    if old_hopital:
        transfer_note += f" ({old_hopital})"
    if target.notes:
        target.notes = transfer_note + " ; " + target.notes
    else:
        target.notes = transfer_note

    _append_source(target, source.source)
    target.date_import = date.today().isoformat()

    warnings.append(
        f"Transfert detecte : {target.titre} {target.nom} {target.prenom} "
        f"({target.specialite}) : {old_city} -> {source.ville}"
    )


def _append_source(target: Doctor, new_source: str):
    """Append a new source label without duplicating."""
    if not new_source:
        return
    existing = set(s.strip() for s in target.source.split("+") if s.strip())
    existing.add(new_source.strip())
    target.source = " + ".join(sorted(existing))


# ---------------------------------------------------------------------------
# Shared matching logic
# ---------------------------------------------------------------------------

def _normalize_for_compare(text: str) -> str:
    """Normalize text for comparison: uppercase, strip accents, remove separators."""
    return strip_accents(text.upper()).replace("-", "").replace(" ", "")


def find_match(
    doc: Doctor,
    existing: list[Doctor],
    cross_city: bool = False,
) -> Doctor | None:
    """Find a matching doctor in the existing list using fuzzy matching.

    If cross_city=True, skip the city check (for transfer detection).
    """
    doc_nom = _normalize_for_compare(doc.nom)
    doc_city = _normalize_for_compare(doc.ville)

    if not doc_nom:
        return None

    best_match = None
    best_score = 999

    for other in existing:
        if not other.nom:
            continue

        # City check (skip if cross-city mode)
        if not cross_city:
            other_city = _normalize_for_compare(other.ville)
            city_dist = edit_distance(doc_city, other_city)
            if city_dist > 3:
                continue

        # Name match
        other_nom = _normalize_for_compare(other.nom)
        name_dist = edit_distance(doc_nom, other_nom)

        if name_dist <= 2 and name_dist < best_score:
            # Check specialty matches (if both have one)
            spec_ok = True
            if doc.specialite and other.specialite:
                spec_ok = doc.specialite == other.specialite

            # For same-city: check sector too
            sector_ok = True
            if not cross_city and doc.secteur and other.secteur:
                sector_ok = doc.secteur == other.secteur

            if spec_ok and sector_ok:
                best_match = other
                best_score = name_dist
                if name_dist == 0:
                    break

    return best_match


def merge_into(target: Doctor, source: Doctor, warnings: list[str]):
    """Merge source data into target record (for merge_all deduplication)."""
    conflicts = []

    if source.completeness_score() > target.completeness_score():
        for field in ["titre", "nom", "prenom", "specialite", "specialite_detail",
                       "secteur", "ville", "region", "type_centre", "responsable_centre"]:
            src_val = getattr(source, field)
            tgt_val = getattr(target, field)
            if src_val and not tgt_val:
                setattr(target, field, src_val)

    for field in ["hopital", "adresse", "telephone", "email"]:
        target_val = getattr(target, field)
        source_val = getattr(source, field)

        if source_val and not target_val:
            setattr(target, field, source_val)
        elif source_val and target_val and source_val != target_val:
            conflicts.append(f"{field}: '{target_val}' vs '{source_val}'")

    _append_source(target, source.source)

    if conflicts:
        warnings.append(
            f"Conflit pour {target.nom} {target.prenom} ({target.ville}): "
            + "; ".join(conflicts)
        )
