# 10 — Ingestion & layout detection

## Accepted inputs

- `.xlsx` / `.xls` (Excel)
- `.docx` (Word)
- Unknown extensions are rejected with a warning; they do not abort the batch.

## Layout classification

Files are classified into one of these layouts, per sheet/document:

| Layout | Shape | Examples |
|---|---|---|
| `TABULAR` | Multi-column grid with a header row (Nom / Specialite / Tel / ...) | Excel exports from hospitals |
| `SINGLE_COLUMN_STATEFUL` | One column, sections (specialty) then field-labeled lines (NOM – PRENOM: ...) | The ASTB reference spreadsheet |
| `PARAGRAPH_SECTIONED` | Word doc with styled headings per city/hospital | "Prise en charge STB" doc |
| `PARAGRAPH_FREETEXT` | Prose with no reliable sections | Fallback when nothing else fits |

## Two-stage pipeline

1. **Scan** (`scan_excel` / `scan_word`) inspects the file once, classifies the layout, builds a `FileTemplate` describing what was found (header rows, field-label positions, section detectors), and buffers the raw content.
2. **Parse** (`generic_parser.parse_with_template`) dispatches by layout and extracts `Doctor` records using the template as a guide.

This split lets one generic parser handle every shape and keeps detection heuristics out of the extraction code.

## Header-row detection (single-column)

The scanner only advances `data_start` past rows it actually recognizes as header content. This means a file that omits the "Centre de competence" or "Responsable : ..." rows still has its first data line parsed.

Recognized header rows:
- Row 0 — city name (mandatory)
- Row 1 — type centre (optional): contains "centre", "competence", or "reference"
- Row 2 — responsable (optional): matches `Responsable\s*:`
- Row 3 — address (optional): matches `Adresse postale\s*:`

## Specialty section detection

Specialty headers are recognized even without a leading number, so files structured as:

```
BORDEAUX
DERMATOLOGUE
Secteur Pediatrie :
NOM – PRENOM : Rossi Lorenzo
...
```

parse correctly. A line qualifies as a specialty header if it is short (< 80 chars), has no `:`, and resolves via `match_specialty`.

## Scavenging (best-effort fallback)

When the structured parser extracts zero doctors from a sheet, the system retries with a freetext scavenger that:
- Looks for `Dr|Pr` prefix names.
- Extracts any email, phone, and known-city mentions.
- Builds a best-effort Doctor record using any fields it can recognize.

A sheet that cannot produce a single doctor emits a warning in the Journal but does not abort the batch.
