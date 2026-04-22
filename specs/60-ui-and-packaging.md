# 60 — UI & packaging

## GUI (Tkinter)

A single window with these controls, in order:
1. **Annuaire existant (optionnel)** — file picker for the existing `.xlsx` annuaire.
2. **Fichiers a importer** — multi-select picker (Word + Excel), list display, add/remove.
3. **Origine** — free-text label stamped on imported records (e.g. "CHU Nantes - avril 2026"). Defaults to filename if empty.
4. **Dossier de sortie** — directory picker; default is a sibling `output/` folder.
5. **Generer / Enrichir** — the primary action button; text toggles based on whether an existing annuaire is loaded.
6. **Status** — single-line progress message.

On completion, a dialog offers to open the produced file.

## Threading

Generation runs on a background `threading.Thread`. Any UI update from the worker must marshal through `root.after(0, ...)` (tk is not thread-safe). The Generate button is disabled during a run and re-enabled in `finally`.

## Packaging (Windows exe)

A single `dist\ASTB_Annuaire.exe` produced by PyInstaller, runnable on machines without Python installed.

- Entry point: `launcher.py` at the project root, which imports `src.main` — this keeps `src/` as a proper package at runtime, so relative imports (`from .scanner import ...`, `from ..normalize import ...`) resolve correctly.
- PyInstaller flags: `--onefile --windowed --collect-submodules src`.
- The `resources/` folder is bundled via `--add-data` but is not read at runtime — only present to satisfy the build script. Do not reference it from application code.
- `build.bat` cleans `build/`, `dist/`, and the spec file before each run, then reports OK / ERROR at the end.

## Supported platforms

- **Windows** — primary target; exe distribution.
- **Linux / macOS** — run via `python3 -m src.main`. No exe is built for these platforms.
