"""Text normalization utilities for French medical directory data."""

import re
import unicodedata


def clean_text(text: str) -> str:
    """Replace non-breaking spaces, collapse whitespace, strip."""
    if not text:
        return ""
    text = text.replace("\xa0", " ")
    text = text.replace("\u200b", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_phone(raw: str) -> str:
    """Normalize French phone numbers to '01 23 45 67 89' format.

    Handles: 0123456789, 01.23.45.67.89, 01 23 45 67 89,
    +33 1 23 45 67 89, (secretariat) labels, multiple numbers separated by / or -.
    Returns multiple numbers separated by ' / '.
    """
    if not raw:
        return ""
    raw = clean_text(raw)
    # Remove common labels but keep the numbers
    raw = re.sub(r"\(?\b(?:secrétariat|secretariat|accueil|standard|rdv)\b\)?", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"(?:Secrétariat|Accueil)\s*:\s*", "", raw)

    # Find all phone-like sequences
    phones = []
    # Match sequences of digits possibly separated by spaces, dots, or dashes
    for m in re.finditer(r"(?:\+33\s*[\s\.\-]?\s*|0)[\d\s\.\-]{8,}", raw):
        digits = re.sub(r"[^\d]", "", m.group())
        # Handle +33 prefix
        if digits.startswith("33") and len(digits) >= 11:
            digits = "0" + digits[2:]
        if len(digits) == 10 and digits.startswith("0"):
            formatted = " ".join([digits[i:i+2] for i in range(0, 10, 2)])
            phones.append(formatted)
        elif len(digits) >= 10:
            # Take first 10 digits
            digits = digits[:10]
            if digits.startswith("0"):
                formatted = " ".join([digits[i:i+2] for i in range(0, 10, 2)])
                phones.append(formatted)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for p in phones:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    return " / ".join(unique)


def normalize_name(raw: str) -> tuple[str, str, str]:
    """Extract (titre, nom, prenom) from a raw name string.

    The source data label is 'NOM – PRENOM', so the expected order is
    LASTNAME Firstname. But the case convention varies:
    - 'LASTNAME Firstname' (clear: uppercase=nom, titlecase=prenom)
    - 'Lastname Firstname' (both titlecase: first word=nom per the label convention)
    - 'LASTNAME FIRSTNAME' (all uppercase: first word=nom, rest=prenom)
    """
    if not raw:
        return ("", "", "")

    raw = clean_text(raw)

    # Extract title
    titre = ""
    title_match = re.match(r"^(Pr(?:ofesseur)?|Dr)\s+", raw, re.IGNORECASE)
    if title_match:
        t = title_match.group(1)
        titre = "Pr" if t.lower().startswith("pr") else "Dr"
        raw = raw[title_match.end():]

    raw = raw.strip()
    if not raw:
        return (titre, "", "")

    # Handle "LASTNAME, Firstname" format (comma-separated)
    if ", " in raw:
        parts = raw.split(", ", 1)
        return (titre, parts[0].upper(), parts[1].strip())

    # Split into words
    words = raw.split()

    def _is_uppercase_word(w):
        core = w.replace("-", "")
        return bool(core and core == core.upper() and core[0].isalpha())

    # Categorize each word as uppercase (nom candidate) or not (prenom candidate)
    upper_indices = [i for i, w in enumerate(words) if _is_uppercase_word(w)]
    lower_indices = [i for i, w in enumerate(words) if not _is_uppercase_word(w)]

    if upper_indices and lower_indices:
        # Mix of uppercase and non-uppercase words
        # Uppercase words = nom, non-uppercase = prenom
        nom_parts = [words[i] for i in upper_indices]
        prenom_parts = [words[i] for i in lower_indices]
        return (titre, " ".join(nom_parts), " ".join(prenom_parts))
    elif upper_indices and not lower_indices:
        # All uppercase - treat first word as nom, rest as prenom
        if len(words) >= 2:
            return (titre, words[0], " ".join(words[1:]))
        return (titre, words[0], "")
    else:
        # No uppercase words - all titlecase
        # First word = nom per NOM-PRENOM label convention
        if len(words) >= 2:
            return (titre, words[0].upper(), " ".join(words[1:]))
        return (titre, words[0].upper() if words else "", "")


def split_multiple_names(raw: str) -> list[str]:
    """Split a multi-doctor name string into individual names.

    Handles separators: ' - ', ' & ', ' et ', ', ' (when followed by uppercase).
    Example: 'SERRANO Emilie - CHERIET Farah' -> ['SERRANO Emilie', 'CHERIET Farah']
    """
    if not raw:
        return []
    raw = clean_text(raw)

    # Split by common separators between doctor names
    # Use lookahead to ensure we split before a new name (uppercase word or title)
    parts = re.split(
        r"\s*(?:[-–]\s+|\s+[-–]\s*|\s*/\s*|\s*&\s*|\s+et\s+|\s*,\s+)(?=[A-ZÀ-ÖÙ-Ý])",
        raw
    )

    result = []
    for part in parts:
        part = part.strip().rstrip(",").strip()
        if part:
            # Skip parts that look like qualifiers rather than names
            if re.match(r"^(?:ou\s+|idem|pas\s+de|en\s+)", part, re.IGNORECASE):
                continue
            result.append(part)

    # Re-join parts that are just a single word (likely a firstname that was
    # separated from the previous lastname by comma, e.g. "LEFORT, Bruno")
    merged = []
    for part in result:
        cleaned = re.sub(r"^(?:Dr|Pr|Professeur)\s+", "", part, flags=re.IGNORECASE).strip()
        if merged and " " not in cleaned and not re.match(r"^(?:Dr|Pr)\s", part, re.IGNORECASE):
            merged[-1] = merged[-1] + ", " + part
        else:
            merged.append(part)

    return merged if merged else [raw] if raw else []


# Regex pattern that matches field labels in concatenated cells
_FIELD_LABEL_PATTERN = re.compile(
    r"(NOM\s*[–\-]\s*PRENOM|"
    r"Hôpital de rattachement|Hopital de rattachement|"
    r"Adresse postale|"
    r"Téléphone|Telephone|"
    r"Adresse mail|Email|"
    r"Secteur)"
    r"\s*:\s*",
    re.IGNORECASE
)


def split_at_field_labels(text: str) -> list[tuple[str, str]]:
    """Split a cell containing concatenated fields into (label, value) pairs.

    Example:
    'Hôpital de rattachement : Robert-Debré Adresse postale : 48 bd...'
    -> [('hopital', 'Robert-Debré'), ('adresse', '48 bd...')]

    Returns normalized label keys:
    'nom', 'hopital', 'adresse', 'telephone', 'email', 'secteur'
    """
    text = clean_text(text)
    if not text:
        return []

    matches = list(_FIELD_LABEL_PATTERN.finditer(text))
    if not matches:
        return [("raw", text)]

    result = []

    # Text before the first label
    prefix = text[:matches[0].start()].strip()
    if prefix:
        result.append(("prefix", prefix))

    for i, m in enumerate(matches):
        label_raw = m.group(1).strip().lower()
        # Normalize label
        if "nom" in label_raw:
            label = "nom"
        elif "hôpital" in label_raw or "hopital" in label_raw:
            label = "hopital"
        elif "adresse postale" in label_raw:
            label = "adresse"
        elif "téléphone" in label_raw or "telephone" in label_raw:
            label = "telephone"
        elif "adresse mail" in label_raw or "email" in label_raw:
            label = "email"
        elif "secteur" in label_raw:
            label = "secteur"
        else:
            label = label_raw

        # Value runs from end of this match to start of next match (or end of string)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        value = text[m.end():end].strip()
        result.append((label, value))

    return result


def normalize_city(raw: str) -> str:
    """Normalize a city name by stripping hospital/CHU prefixes."""
    if not raw:
        return ""
    raw = clean_text(raw)
    # Remove common prefixes
    raw = re.sub(
        r"^(?:CHU\s+(?:de\s+)?|CHRU\s+(?:de\s+)?|Centre\s+Hospitalier\s+(?:de\s+)?|"
        r"Hôpital\s+|Hopital\s+)",
        "", raw, flags=re.IGNORECASE
    )
    return raw.strip()


def strip_accents(text: str) -> str:
    """Remove diacritical marks for comparison purposes."""
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def edit_distance(a: str, b: str) -> int:
    """Simple Levenshtein edit distance for fuzzy name matching."""
    if len(a) < len(b):
        return edit_distance(b, a)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr

    return prev[-1]
