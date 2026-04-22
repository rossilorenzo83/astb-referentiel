"""Consolidated French medical directory field and specialty synonym dictionary."""

import re
import jellyfish

from ..normalize import strip_accents

# Canonical specialties that participate in phonetic matching. Computed once.
_CANONICAL_SPECIALTIES = (
    "NEPHROLOGIE", "PNEUMOLOGIE", "PSYCHIATRIE", "GENETIQUE", "OPHTALMOLOGIE",
    "CARDIOLOGIE", "DERMATOLOGIE", "NEUROLOGIE", "UROLOGIE", "RHUMATOLOGIE",
)
_CANONICAL_METAPHONES = {
    jellyfish.metaphone(s.lower()): s for s in _CANONICAL_SPECIALTIES
}

# Tracks the last phonetic-ambiguity reason so the caller can surface it.
_last_phonetic_warning: list[str] = []


def consume_phonetic_warnings() -> list[str]:
    """Return and clear any pending phonetic-ambiguity messages."""
    msgs = list(_last_phonetic_warning)
    _last_phonetic_warning.clear()
    return msgs

# Maps Doctor field name -> list of (pattern, is_regex) synonyms.
# Non-regex patterns matched case-insensitively after accent stripping.
FIELD_SYNONYMS: dict[str, list[tuple[str, bool]]] = {
    "nom": [
        (r"NOM\s*[–\-]\s*PRENOM", True),
        ("nom", False),
        ("medecin", False),
        ("praticien", False),
        ("referent", False),
    ],
    "prenom": [
        ("prenom", False),
    ],
    "hopital": [
        (r"H[oô]pital\s+de\s+rattachement", True),
        ("hopital", False),
        ("etablissement", False),
        ("centre hospitalier", False),
        ("service", False),
    ],
    "adresse": [
        ("adresse postale", False),
        ("adresse", False),
    ],
    "telephone": [
        (r"T[ée]l[ée]phone", True),
        ("tel.", False),
        ("tel", False),
        ("telephone", False),
    ],
    "email": [
        ("adresse mail", False),
        ("adresse email", False),
        ("e-mail", False),
        ("email", False),
        ("mail", False),
        ("courriel", False),
    ],
    "specialite": [
        ("specialite", False),
        ("discipline", False),
    ],
    "secteur": [
        ("secteur", False),
    ],
    "ville": [
        ("ville", False),
        ("site", False),
    ],
}

# Specialty text -> canonical specialty name
SPECIALTY_SYNONYMS: dict[str, str] = {
    "nephrologues": "NEPHROLOGIE",
    "nephrologie": "NEPHROLOGIE",
    "pneumologues": "PNEUMOLOGIE",
    "pneumologie": "PNEUMOLOGIE",
    "psychiatres": "PSYCHIATRIE",
    "psychiatrie": "PSYCHIATRIE",
    "geneticiens": "GENETIQUE",
    "genetique": "GENETIQUE",
    "ophtalmologues": "OPHTALMOLOGIE",
    "ophtalmologie": "OPHTALMOLOGIE",
    "cardiologues": "CARDIOLOGIE",
    "cardiolologues": "CARDIOLOGIE",
    "cardiologie": "CARDIOLOGIE",
    "dermatologues": "DERMATOLOGIE",
    "dermatologie": "DERMATOLOGIE",
    "neurologues": "NEUROLOGIE",
    "neurologie": "NEUROLOGIE",
    "urologues": "UROLOGIE",
    "urologie": "UROLOGIE",
    "rhumatologues": "RHUMATOLOGIE",
    "rhumatologie": "RHUMATOLOGIE",
    "autres specialites": "AUTRE",
}

# Partial prefix matching for specialty detection in free text
SPECIALTY_PREFIXES: dict[str, str] = {
    "nephro": "NEPHROLOGIE",
    "pneumo": "PNEUMOLOGIE",
    "psychiatr": "PSYCHIATRIE",
    "genet": "GENETIQUE",
    "ophtalmo": "OPHTALMOLOGIE",
    "cardio": "CARDIOLOGIE",
    "dermato": "DERMATOLOGIE",
    "neuro": "NEUROLOGIE",
    "urolog": "UROLOGIE",
    "rhumato": "RHUMATOLOGIE",
}


def match_field_synonym(text: str) -> str | None:
    """Return the Doctor field name if text matches a known synonym, else None.

    Checks all patterns and returns the one with the longest matching synonym,
    so 'adresse mail' matches 'email' not 'adresse'.
    """
    if not text:
        return None
    normalized = strip_accents(text.strip().lower())
    best_field = None
    best_length = 0
    for field_name, patterns in FIELD_SYNONYMS.items():
        for pattern, is_regex in patterns:
            if is_regex:
                m = re.search(pattern, text, re.IGNORECASE)
                if m and len(m.group()) > best_length:
                    best_field = field_name
                    best_length = len(m.group())
            else:
                pat_norm = strip_accents(pattern.lower())
                if pat_norm in normalized and len(pat_norm) > best_length:
                    best_field = field_name
                    best_length = len(pat_norm)
    return best_field


def classify_specialty(text: str) -> tuple[str | None, str | None]:
    """Return (canonical_specialty, method) for a raw specialty string.

    method is one of "exact", "prefix", "fuzzy", "phonetic", or None.
    Callers use the method to mark cells resolved by a non-exact path.
    """
    if not text:
        return (None, None)
    normalized = strip_accents(text.strip().lower()).rstrip(":").strip()
    if normalized in SPECIALTY_SYNONYMS:
        return (SPECIALTY_SYNONYMS[normalized], "exact")
    for prefix, spec in SPECIALTY_PREFIXES.items():
        if normalized.startswith(prefix):
            return (spec, "prefix")
    from ..normalize import edit_distance
    for prefix, spec in SPECIALTY_PREFIXES.items():
        if len(prefix) < 6:
            continue
        head = normalized[: len(prefix)]
        if len(head) == len(prefix) and edit_distance(head, prefix) <= 1:
            return (spec, "fuzzy")
    code = jellyfish.metaphone(normalized)
    if code:
        matches = [spec for c, spec in _CANONICAL_METAPHONES.items() if c == code]
        if len(matches) == 1:
            return (matches[0], "phonetic")
        if len(matches) > 1:
            _last_phonetic_warning.append(
                f"[Phonetique] '{text}' correspond a plusieurs specialites "
                f"({', '.join(matches)}) — non resolu"
            )
    return (None, None)


def match_specialty(text: str) -> str | None:
    """Return canonical specialty name if text matches, else None."""
    return classify_specialty(text)[0]
