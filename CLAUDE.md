# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Specifications

Behavior requirements live in `specs/`. Before changing parser, merge, or output behavior, read the relevant spec file first and update it if the behavior is changing. `specs/README.md` is the index.

## Project

Tool for the ASTB association (Sclerose Tuberuse de Bourneville) that ingests heterogeneous Word/Excel files of doctor contacts and produces a single structured Excel directory. Two modes: build from scratch, or enrich an existing directory (preserves all data, detects doctor transfers between cities).

## Commands

```bash
# Run the GUI app (must use -m; src/main.py uses relative imports)
python -m src.main               # Windows
python3 -m src.main              # Linux/macOS
# or double-click run.bat

# Install deps (runtime + test)
pip install -r requirements.txt

# Run all tests (123 tests, synthetic fixtures — no resource files needed)
python -m unittest discover -s tests -v

# Single test file / method
python -m unittest tests.test_enrichment
python -m unittest tests.test_enrichment.TestEnrichment.test_transfer_detection

# Build Windows .exe (produces dist/ASTB_Annuaire.exe)
build.bat
```

**Build gotcha:** `build.bat` passes `--add-data "resources;resources"`, but the `resources/` folder is gitignored and often absent on fresh clones. Without it, PyInstaller fails silently and `dist/` stays empty. Either create an empty `resources/` folder before building or drop `--add-data` from the command — the app does not read anything from `resources/` at runtime (only tests do, and they use synthetic fixtures from `tests/conftest.py`).

## Architecture

### Two-stage scanner pipeline

Parsing is split into **scan** (structure inference) and **parse** (data extraction), connected by a `FileTemplate` describing the file's layout. This lets one generic parser handle all file shapes.

```
scan_and_parse(path)         # src/scanner/__init__.py
  -> scan_excel | scan_word  # inspects file, classifies layout
      -> FileTemplate        # src/scanner/template.py
  -> parse_with_template     # src/scanner/generic_parser.py
      -> dispatch by LayoutType
      -> list[Doctor]
```

`LayoutType` values (`template.py`): `TABULAR`, `SINGLE_COLUMN_STATEFUL`, `PARAGRAPH_SECTIONED`, `PARAGRAPH_FREETEXT`. Field labels are resolved via French synonym dictionaries in `src/scanner/synonyms.py` (e.g. "Tel.", "Tél", "Telephone" all map to `telephone`). When adding a new field variant, extend `synonyms.py` — don't special-case it in the parser.

### Doctor model and deduplication

`Doctor` (`src/models.py`) has 17 fields plus a computed `region` (from `CITY_TO_REGION`). The critical invariants:

- `dedup_key()` returns `(ville, normalized_nom, specialite)` — accent-stripped, uppercase, hyphens/spaces removed. This is the join key for both merging and enrichment.
- `completeness_score()` — when two records match, the more complete one wins field-by-field.

When adding new cities, update `CITY_TO_REGION` in `models.py`. The prefix fallback in `get_region()` handles compound names ("Paris Robert Debre" -> "Ile-de-France").

### Merge vs enrich (not interchangeable)

Both live in `src/merge.py`:

- `merge_all(doctors)` — used for **first-time generation** from imported files. Deduplicates across sources, merges fields.
- `enrich(existing, new_doctors)` — used when an **annuaire already exists**. Never deletes existing records; same-city match updates fields, cross-city match is treated as a **transfer** (updates location, logs "Transfere de ..." in notes).

`main.py` picks between them based on whether the user provided an existing annuaire path. Preserve the no-delete invariant when modifying `enrich`.

### Output: three Excel sheets

`writer_excel.py` emits one workbook with: `Annuaire Complet` (filterable, frozen header, 17 columns per `COLUMN_HEADERS`), `Par Ville` (pivot city x specialty), `Journal Import` (warnings/conflicts/transfers). The column order in `COLUMN_HEADERS` and `doctor_to_row()` must stay in sync — readers parse by position.

### GUI threading

`main.py` runs generation on a background `threading.Thread` and marshals updates to the Tk thread via `root.after(0, ...)`. Any new UI work from worker threads must go through `_update_status` or `root.after` — direct Tk calls from the worker will crash on Windows.

## Tests

`tests/conftest.py` programmatically generates synthetic Excel/Word fixtures in a temp dir via `get_fixture_dir()` — the full suite runs without any real data in `resources/`. Integration tests in `test_parsers.py` reference these fixtures. CI (`.github/workflows/ci.yml`) runs tests on Ubuntu + Windows across Python 3.10/3.11/3.12 and builds the Windows exe as an artifact.
