# 00 — Overview

## Purpose

Build and maintain a single structured directory of doctors who take care of STB (Sclerose Tubereuse de Bourneville) patients in France, for the ASTB patient association.

## Actors

- **ASTB volunteer** — receives heterogeneous files (Word/Excel) from hospitals or contacts, wants a single searchable annuaire to answer family requests.
- **Family member** (indirect) — consumes the produced Excel, filters by region/ville/specialite.

## Constraints

- Input files are **not standardized**: some are tables with clean headers, some are single-column lists with free text, some are Word paragraphs.
- File quality is **unreliable**: typos in specialty names, inconsistent casing, first/last name order, broken encodings, concatenated fields in a single cell.
- The tool must **never lose data** from a previous annuaire — enrichment is additive.
- Personal data cannot be published: source files live in `resources/` (gitignored); tests use synthetic fixtures.

## End-to-end flow

```
User selects input files (+ optional existing annuaire)
        |
        v
Per file: scan_and_parse -> list[Doctor]
        |
        v
  - Generation mode: merge_all(new)    -> dedup, field merge
  - Enrichment mode: enrich(existing, new) -> no deletes, detect transfers
        |
        v
  write_excel -> Annuaire_Medecins_STB.xlsx (3 sheets)
```

## Non-goals

- No web/API surface.
- No automatic email/CRM integration.
- No OCR or PDF parsing.
