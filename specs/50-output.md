# 50 — Output

The tool writes a single Excel workbook `Annuaire_Medecins_STB.xlsx` with three sheets.

## Sheet 1 — Annuaire Complet

- 17 columns in the exact order of `COLUMN_HEADERS`.
- Header row frozen; auto-filter enabled on all columns.
- Sorted by `region`, then `ville`, then `specialite`, then `nom`.
- Column widths tuned for readability (wider for address/notes/hopital, narrower for region/titre).

### Cell highlighting (conflicts & inference)

Specific cells carry a visual marker so a reviewer can spot rows needing attention without scanning the Journal:

| Cell state | Fill color | Cell comment |
|---|---|---|
| `Hopital` on a row flagged as hospital conflict (see `specs/40-merge-and-enrich.md`) | Yellow | `Conflit: voir aussi <other hopital>` |
| `Adresse` / `Telephone` / `Email` filled by sibling inference | Light blue | `Inferé depuis <hopital>` |
| `Specialite` resolved via phonetic fallback or typo correction | Light gray | `Resolu depuis: <original text>` |

Colors are chosen to remain readable when the sheet is printed in grayscale; the cell comment carries the authoritative explanation regardless of color.

A conditional-format legend is added as a small frozen block above the data region in row 0–1 (above the header) so recipients understand the colors without opening cell comments.

## Sheet 2 — Par Ville

Pivot-style cross-tab: rows = villes, columns = specialties, values = count of doctors. Useful for spotting gaps (e.g. no nephrologist in city X).

## Sheet 3 — Journal Import

Chronological log emitted during the run:
- **Scanner warnings**: layout classification issues, short sheets, unrecognized headers.
- **Parser warnings**: format-not-recognized, freetext fallback used, ambiguous names, phonetic ambiguity.
- **Merge/enrich events**: conflicts, transfers detected, hospital conflicts requiring manual review, inferred values.

Each entry includes (when applicable) the doctor's name, specialty, ville, hospital, and a short action hint (e.g. `revue manuelle requise`, `resolu automatiquement`). Hospital-conflict entries link back to the two row numbers involved in the Annuaire Complet sheet.

The journal is the single trail users consult to audit what the tool did with their input.

## Filenames

- Generation and enrichment both write to `Annuaire_Medecins_STB.xlsx` in the user-selected output directory. Enrichment overwrites the file — no backup is made automatically; users are expected to version the file themselves (timestamped folder, git, etc.).
