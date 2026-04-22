# Specifications

This folder is the single source of truth for product/behavior requirements. Each file is one focused spec. Code must match what is written here; when behavior changes, edit the spec first, then the code.

## Index

- [00-overview.md](00-overview.md) — what the tool does, actors, end-to-end flow
- [10-ingestion.md](10-ingestion.md) — accepted inputs, layout detection, scavenging from unstructured files
- [20-field-extraction.md](20-field-extraction.md) — field labels, synonyms, specialty resolution (incl. phonetic)
- [21-name-parsing.md](21-name-parsing.md) — NOM/PRENOM extraction, title handling, first/last name swap detection
- [30-doctor-model.md](30-doctor-model.md) — the `Doctor` record (17 fields), region mapping, dedup key
- [40-merge-and-enrich.md](40-merge-and-enrich.md) — generation vs enrichment, transfer detection, no-delete invariant
- [50-output.md](50-output.md) — Excel output: 3 sheets, column order, journal
- [60-ui-and-packaging.md](60-ui-and-packaging.md) — Tkinter GUI, threading, PyInstaller exe
