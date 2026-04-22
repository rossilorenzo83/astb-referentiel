# 30 — Doctor model

## Fields (17, in column order)

| # | Field | Notes |
|---|---|---|
| 1 | `region` | Derived from `ville` via `CITY_TO_REGION`. |
| 2 | `ville` | Source of truth; region follows from it. |
| 3 | `type_centre` | e.g. "Centre de competence", "Centre de reference". |
| 4 | `responsable_centre` | Lead coordinator for the center (sheet-level, not per doctor). |
| 5 | `specialite` | Canonical form from `SPECIALTY_MAP` (NEPHROLOGIE, DERMATOLOGIE, ...). |
| 6 | `specialite_detail` | Free text when specialty is AUTRE or when a sub-discipline is given. |
| 7 | `secteur` | `Pediatrie`, `Adulte`, `Pediatrie et Adulte`, or `Non precise`. |
| 8 | `titre` | `Dr` or `Pr`. Empty if unknown. |
| 9 | `nom` | Uppercase family name. |
| 10 | `prenom` | Titlecase given name(s). |
| 11 | `hopital` | Hospital or service where the doctor practices. |
| 12 | `adresse` | Postal address. |
| 13 | `telephone` | Normalized to `NN NN NN NN NN`; multiple separated by ` / `. |
| 14 | `email` | One email, or multiple joined with ` ; `. |
| 15 | `notes` | Free text: transfers, idem references, qualifiers. |
| 16 | `source` | Origin label (user-provided "Origine" field, else filename). |
| 17 | `date_import` | ISO date, set at record creation. |

`COLUMN_HEADERS` and `doctor_to_row` must stay in sync with this list — readers parse by position.

## Derived properties

- **Region mapping** (`CITY_TO_REGION` in `src/models.py`) covers all cities currently seen in ASTB sources, plus a prefix fallback for compound names ("Paris Robert Debre" → Ile-de-France). New cities are added to this dict.
- **Dedup key** = `(accent-stripped uppercase ville, accent-stripped uppercase nom with hyphens/spaces removed, specialite)`.
- **Emptiness** = no `nom` **and** no `notes`; empty doctors are dropped.
- **Completeness score** = count of non-empty values among `{nom, prenom, hopital, adresse, telephone, email}`; used as tie-breaker during merge.
