# 20 — Field extraction & specialty resolution

## Field synonym dictionary

Field labels in source files vary wildly. The synonym dictionary in `src/scanner/synonyms.py` maps any recognized label to a canonical `Doctor` field name:

| Canonical field | Recognized labels (case-insensitive, accent-insensitive) |
|---|---|
| `nom` | `NOM – PRENOM`, `nom`, `medecin`, `praticien`, `referent` |
| `prenom` | `prenom` |
| `hopital` | `Hopital de rattachement`, `hopital`, `etablissement`, `centre hospitalier`, `service` |
| `adresse` | `adresse postale`, `adresse` |
| `telephone` | `Telephone`, `tel.`, `tel`, `telephone` |
| `email` | `adresse mail`, `adresse email`, `e-mail`, `email`, `mail`, `courriel` |
| `specialite` | `specialite`, `discipline` |
| `secteur` | `secteur` |
| `ville` | `ville`, `site` |

Synonyms are matched **longest-wins** so `adresse mail` maps to `email`, not `adresse`.

## Concatenated cells

A single cell may contain several labeled fields glued together, e.g.:

```
Hopital de rattachement : Robert-Debre Adresse postale : 48 bd ... Telephone : 01 40 ... Adresse mail : foo@bar.fr
```

`normalize.split_at_field_labels` slices such a string at label boundaries and returns `[(field, value), ...]`. The parser feeds these into the current doctor record.

## Specialty resolution

Both **discipline** names (`dermatologie`) and **practitioner** names (`dermatologue`, `dermatologues`) must resolve to the same canonical specialty. A random header may use either form, in any case, possibly with typos.

### Matching order

`match_specialty(text)` tries, in order:

1. **Exact synonym match** against `SPECIALTY_SYNONYMS` after lowercasing and accent-stripping (e.g. `dermatologues` → `DERMATOLOGIE`, `genetiques` → `GENETIQUE`).
2. **Prefix match** against `SPECIALTY_PREFIXES` (e.g. `dermato...` → `DERMATOLOGIE`).
3. **Fuzzy edit-distance match** on the head of the text against each prefix, `<= 1` edit (typo tolerance). Only prefixes of length `>= 6` are eligible to avoid cross-specialty false positives (short prefixes like `neuro`/`genet` would otherwise absorb variants of other specialties).
4. **Phonetic match** *(new — see below)*.

### Phonetic fallback

A French-appropriate phonetic algorithm (Soundex-FR or Metaphone) is used as a last resort before returning `None`. It must:

- Collapse common French homophones (ph/f, ch/k where applicable, silent trailing letters).
- Handle non-French spellings when the consonant skeleton matches (e.g. `NEFROLOGIE` → `NEPHROLOGIE`: f↔ph).
- **Not** collapse distinct specialties that happen to share a head (e.g. `neuro*` must not phonetically match `nephro*`).

Implementation: use the `metaphone` library's Double Metaphone (or `jellyfish.metaphone`). Both specialty canonical forms and the input are encoded, and a direct code equality is required. This is strictly a fallback — if steps 1–3 return a result, phonetic matching is not consulted.

Known specialties in the dictionary (canonical forms): NEPHROLOGIE, PNEUMOLOGIE, PSYCHIATRIE, GENETIQUE, OPHTALMOLOGIE, CARDIOLOGIE, DERMATOLOGIE, NEUROLOGIE, UROLOGIE, RHUMATOLOGIE, AUTRE.

### Ambiguity & confidence

If phonetic matching produces **multiple candidate specialties with equal confidence**, the input is rejected (return `None`) and a warning is emitted in the Journal. Never silently pick one.

## Field post-processing

- Phones are normalized by `normalize_phone` to `NN NN NN NN NN`. `+33` is converted to leading `0`. Multiple numbers are joined with ` / `.
- Emails are stripped of trailing `(...)` notes and leading `:` / whitespace.
- Specialty text is uppercased before lookup; the canonical form is stored.
- A specialty labeled `AUTRE` with a detail that itself resolves to a known specialty is **reclassified** to that specialty (e.g. `AUTRES SPECIALITES, preciser : Neurologie` → `NEUROLOGIE`).
