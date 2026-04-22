"""Merge, deduplication, and enrichment logic for doctor records."""

import re
from collections import Counter, defaultdict
from datetime import date

from .models import Doctor, get_region
from .normalize import strip_accents, edit_distance


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def merge_all(doctors_list: list[Doctor]) -> tuple[list[Doctor], list[str]]:
    """Deduplicate a flat list of doctors from any number of sources."""
    warnings: list[str] = []
    merged: list[Doctor] = []

    for doc in doctors_list:
        if not doc.nom:
            merged.append(doc)
            continue

        # Try same-city + same-hospital match first (safe merge)
        same = _find_match(doc, merged, same_city=True, same_hopital=True)
        if same:
            merge_into(same, doc, warnings)
            continue

        # Same nom + specialite somewhere else (different ville or hopital)?
        other = _find_match(doc, merged, same_city=False, same_hopital=False)
        if other:
            if _is_explicit_transfer(doc):
                _apply_transfer(other, doc, warnings)
            elif _hopitals_differ(other, doc):
                _flag_hospital_conflict(other, doc, warnings)
                merged.append(doc)
            else:
                # Same nom/spec/hopital, only ville differs: likely a data
                # entry slip; merge into the existing record and warn.
                merge_into(other, doc, warnings)
            continue

        merged.append(doc)

    _infer_from_siblings(merged, warnings)
    return merged, warnings


def enrich(
    existing: list[Doctor],
    new_doctors: list[Doctor],
) -> tuple[list[Doctor], list[str]]:
    """Enrich an existing annuaire with new doctor records.

    - Same ville + same hopital: merge fields.
    - Same name/specialty with different hopital (same or other ville):
      hospital conflict (keep both, cross-link, mark for review) unless the
      new record explicitly signals a transfer.
    - No match: append as new.
    - Never deletes existing records.
    """
    warnings: list[str] = []
    result = list(existing)

    for new_doc in new_doctors:
        if not new_doc.nom:
            continue

        same = _find_match(new_doc, result, same_city=True, same_hopital=True)
        if same:
            _enrich_merge(same, new_doc, warnings)
            continue

        other = _find_match(new_doc, result, same_city=False, same_hopital=False)
        if other:
            if _is_explicit_transfer(new_doc):
                _apply_transfer(other, new_doc, warnings)
            elif _hopitals_differ(other, new_doc):
                _flag_hospital_conflict(other, new_doc, warnings)
                result.append(new_doc)
            else:
                # Same nom/spec/hopital, only ville differs: treat as update
                _enrich_merge(other, new_doc, warnings)
            continue

        result.append(new_doc)
        warnings.append(
            f"Nouveau medecin ajoute : {new_doc.titre} {new_doc.nom} {new_doc.prenom} "
            f"({new_doc.ville}, {new_doc.specialite})"
        )

    _infer_from_siblings(result, warnings)
    return result, warnings


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _normalize_for_compare(text: str) -> str:
    return strip_accents(text.upper()).replace("-", "").replace(" ", "")


def _normalize_hopital(raw: str) -> str:
    """Normalize a hospital name for sibling/conflict comparison.

    Strips accents, common establishment prefixes (CHU, CHRU, Hopital,
    Centre Hospitalier...), and punctuation. Case-insensitive.
    """
    if not raw:
        return ""
    s = strip_accents(raw).lower()
    s = re.sub(
        r"\b(?:chu|chru|hopital|hopitaux|centre\s+hospitalier|"
        r"centre\s+de\s+reference|centre\s+de\s+competence)\b",
        " ", s,
    )
    s = re.sub(r"\bd['\s]", " ", s)  # "de ", "d'"
    s = re.sub(r"\bde\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def _find_match(
    doc: Doctor,
    pool: list[Doctor],
    *,
    same_city: bool,
    same_hopital: bool,
) -> Doctor | None:
    """Find a Doctor in `pool` matching doc on nom + specialite, with
    optional ville and hopital constraints. Returns the best (lowest name
    edit-distance) match or None."""
    doc_nom = _normalize_for_compare(doc.nom)
    if not doc_nom:
        return None
    doc_city = _normalize_for_compare(doc.ville)
    doc_hop = _normalize_hopital(doc.hopital)

    best, best_score = None, 999
    for other in pool:
        if not other.nom:
            continue
        if same_city:
            if edit_distance(doc_city, _normalize_for_compare(other.ville)) > 3:
                continue
        if same_hopital:
            other_hop = _normalize_hopital(other.hopital)
            if doc_hop and other_hop and doc_hop != other_hop:
                continue
            if bool(doc_hop) != bool(other_hop):
                # One side has no hopital — don't require match, but also don't
                # force same_hopital rejection (lets records with missing hop
                # still merge within the same ville).
                pass

        name_dist = edit_distance(doc_nom, _normalize_for_compare(other.nom))
        if name_dist > 2:
            continue
        if doc.specialite and other.specialite and doc.specialite != other.specialite:
            continue
        if name_dist < best_score:
            best, best_score = other, name_dist
            if name_dist == 0:
                break
    return best


def _hopitals_differ(a: Doctor, b: Doctor) -> bool:
    na, nb = _normalize_hopital(a.hopital), _normalize_hopital(b.hopital)
    return bool(na and nb and na != nb)


# ---------------------------------------------------------------------------
# Transfer vs conflict
# ---------------------------------------------------------------------------

_TRANSFER_RE = re.compile(
    r"transfer[eé]+\s+(?:de|depuis)\b|\bmut[eé]+\b|ancienn?e?\s+affect",
    re.IGNORECASE,
)


def _is_explicit_transfer(doc: Doctor) -> bool:
    """True if the doc's notes/source signal an explicit transfer event."""
    blob = f"{doc.notes} {doc.source}"
    return bool(_TRANSFER_RE.search(strip_accents(blob)))


def _apply_transfer(target: Doctor, new: Doctor, warnings: list[str]):
    """Collapse a transfer: update target with new affiliation, note the move."""
    old_city = target.ville
    old_hop = target.hopital
    target.ville = new.ville or target.ville
    target.region = get_region(target.ville)
    for f in ("hopital", "adresse", "telephone", "email",
              "type_centre", "responsable_centre"):
        v = getattr(new, f)
        if v:
            setattr(target, f, v)
    for f in ("titre", "prenom", "specialite", "specialite_detail", "secteur"):
        if getattr(new, f) and not getattr(target, f):
            setattr(target, f, getattr(new, f))
    note = f"Transfere de {old_city}" + (f" ({old_hop})" if old_hop else "")
    target.notes = note + (" ; " + target.notes if target.notes else "")
    _append_source(target, new.source)
    target.date_import = date.today().isoformat()
    # Clear any previous conflict marker on hopital
    target.markers.pop("hopital", None)
    warnings.append(
        f"Transfert detecte : {target.titre} {target.nom} {target.prenom} "
        f"({target.specialite}) : {old_city} -> {new.ville}"
    )


def _flag_hospital_conflict(a: Doctor, b: Doctor, warnings: list[str]):
    """Mark two records as belonging to a same-doctor / different-hopital
    conflict that requires human review. Both are kept."""
    for rec, other in ((a, b), (b, a)):
        comment = f"Conflit: voir aussi {other.hopital or other.ville}"
        rec.markers["hopital"] = {"kind": "conflict", "comment": comment}
        note = f"Affiliation multiple possible — voir aussi {other.hopital or other.ville}"
        if note not in rec.notes:
            rec.notes = note + (" ; " + rec.notes if rec.notes else "")
    warnings.append(
        f"[Conflit hopital] {a.titre} {a.nom} {a.prenom} ({a.specialite}): "
        f"{a.hopital or '(inconnu)'} et {b.hopital or '(inconnu)'} — revue manuelle requise"
    )


# ---------------------------------------------------------------------------
# Field-level merging
# ---------------------------------------------------------------------------

def _enrich_merge(target: Doctor, source: Doctor, warnings: list[str]):
    """Merge new data into an existing record (same ville, same hopital)."""
    conflicts = []
    for f in ("hopital", "adresse", "telephone", "email"):
        t, s = getattr(target, f), getattr(source, f)
        if s and not t:
            setattr(target, f, s)
        elif s and t and s != t:
            conflicts.append(f"{f}: '{t}' -> '{s}'")
            setattr(target, f, s)
    for f in ("titre", "prenom", "specialite", "specialite_detail",
              "secteur", "type_centre", "responsable_centre"):
        if getattr(source, f) and not getattr(target, f):
            setattr(target, f, getattr(source, f))
    _append_source(target, source.source)
    target.date_import = date.today().isoformat()
    if conflicts:
        warnings.append(
            f"Mise a jour {target.nom} {target.prenom} ({target.ville}): "
            + "; ".join(conflicts)
        )


def merge_into(target: Doctor, source: Doctor, warnings: list[str]):
    """Merge source into target for `merge_all` deduplication."""
    conflicts = []
    if source.completeness_score() > target.completeness_score():
        for f in ("titre", "nom", "prenom", "specialite", "specialite_detail",
                  "secteur", "ville", "region", "type_centre", "responsable_centre"):
            sv, tv = getattr(source, f), getattr(target, f)
            if sv and not tv:
                setattr(target, f, sv)
    for f in ("hopital", "adresse", "telephone", "email"):
        tv, sv = getattr(target, f), getattr(source, f)
        if sv and not tv:
            setattr(target, f, sv)
        elif sv and tv and sv != tv:
            conflicts.append(f"{f}: '{tv}' vs '{sv}'")
    _append_source(target, source.source)
    if conflicts:
        warnings.append(
            f"Conflit pour {target.nom} {target.prenom} ({target.ville}): "
            + "; ".join(conflicts)
        )


def _append_source(target: Doctor, new_source: str):
    if not new_source:
        return
    existing = set(s.strip() for s in target.source.split("+") if s.strip())
    existing.add(new_source.strip())
    target.source = " + ".join(sorted(existing))


# Preserve old `find_match` name for tests that import it directly.
def find_match(
    doc: Doctor,
    existing: list[Doctor],
    cross_city: bool = False,
) -> Doctor | None:
    return _find_match(
        doc, existing, same_city=not cross_city, same_hopital=False
    )


# ---------------------------------------------------------------------------
# Sibling-based inference
# ---------------------------------------------------------------------------

_SECRETARIAT_HINT = re.compile(r"secretariat|accueil|standard", re.IGNORECASE)


def _infer_from_siblings(doctors: list[Doctor], warnings: list[str]):
    """Fill empty adresse / telephone / email from same-hopital siblings.

    A value is considered shared (secretariat-style) when it is labeled as
    such OR appears on >= 2 records in the group. Personal values seen on
    a single record are NOT propagated. Ambiguous groups (siblings disagree)
    leave the field empty and log a warning.
    """
    groups: dict[tuple[str, str], list[Doctor]] = defaultdict(list)
    for doc in doctors:
        hop = _normalize_hopital(doc.hopital)
        if not hop:
            continue
        ville = strip_accents(doc.ville.lower()).strip()
        groups[(ville, hop)].append(doc)

    for (_, _), members in groups.items():
        if len(members) < 2:
            continue
        display_hop = next((m.hopital for m in members if m.hopital), "")

        # adresse: any non-empty value among siblings qualifies (hospital
        # address is universally shared).
        adresse_values = Counter(m.adresse.strip() for m in members if m.adresse.strip())
        adresse_shared = _pick_shared(adresse_values, require_repeat=False)

        # telephone / email: only propagate values that are shared (>= 2
        # occurrences) or explicitly labeled secretariat.
        tel_shared = _pick_shared_contact(members, "telephone")
        email_shared = _pick_shared_contact(members, "email")

        for rec in members:
            _fill_if_missing(rec, "adresse", adresse_shared, display_hop, warnings)
            _fill_if_missing(rec, "telephone", tel_shared, display_hop, warnings)
            _fill_if_missing(rec, "email", email_shared, display_hop, warnings)


def _pick_shared(counter: Counter, *, require_repeat: bool):
    """Return the shared value from a Counter, or None if ambiguous/absent.

    require_repeat=True: only values seen >= 2 times qualify.
    require_repeat=False: any single value qualifies; if multiple distinct
    values exist, the field is ambiguous and we return the sentinel (None,
    sorted tuple of values) so the caller can emit a warning.
    """
    if not counter:
        return None
    items = list(counter.items())
    if require_repeat:
        items = [(v, c) for v, c in items if c >= 2]
        if not items:
            return None
    values = {v for v, _ in items}
    if len(values) == 1:
        return next(iter(values))
    return ("AMBIGUOUS", tuple(sorted(values)))


def _pick_shared_contact(members: list[Doctor], field: str):
    """Pick a shared phone/email across siblings. Labeled secretariat values
    outrank unlabeled ones; single-occurrence unlabeled values don't propagate."""
    labeled: list[str] = []
    seen: Counter = Counter()
    for m in members:
        val = (getattr(m, field) or "").strip()
        if not val:
            continue
        seen[val] += 1
        ctx = f"{m.notes} {m.adresse}"
        if _SECRETARIAT_HINT.search(ctx):
            labeled.append(val)
    if labeled:
        uniq = set(labeled)
        if len(uniq) == 1:
            return next(iter(uniq))
        return ("AMBIGUOUS", tuple(sorted(uniq)))
    return _pick_shared(seen, require_repeat=True)


def _fill_if_missing(
    rec: Doctor, field: str, shared, hop_label: str, warnings: list[str]
):
    if getattr(rec, field):
        return
    if shared is None:
        return
    if isinstance(shared, tuple) and shared[0] == "AMBIGUOUS":
        warnings.append(
            f"[Inference] {field} ambigu pour {rec.titre} {rec.nom} "
            f"({hop_label}): valeurs {shared[1]} — laisse vide"
        )
        return
    setattr(rec, field, shared)
    rec.markers[field] = {
        "kind": "inferred",
        "comment": f"Infere depuis secretariat {hop_label}",
    }
    note = f"{field} infere depuis secretariat {hop_label}"
    if note not in rec.notes:
        rec.notes = (rec.notes + " ; " if rec.notes else "") + note
