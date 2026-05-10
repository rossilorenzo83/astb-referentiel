"""Cross-platform build script for the ASTB Annuaire executable.

Works the same from cmd.exe, PowerShell, Git Bash, WSL, Linux, or macOS.
Run: python build.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
APP_NAME = "ASTB_Annuaire"
ENTRY = "launcher.py"


def _run(cmd: list[str]) -> None:
    print(">>>", " ".join(cmd), flush=True)
    subprocess.check_call(cmd)


def main() -> None:
    os.chdir(ROOT)

    print("Installing dependencies...")
    _run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    _run([sys.executable, "-m", "pip", "install", "pyinstaller"])

    print("\nCleaning previous builds...")
    for path in ("build", "dist", f"{APP_NAME}.spec"):
        p = ROOT / path
        if p.is_dir():
            shutil.rmtree(p)
        elif p.is_file():
            p.unlink()

    print("\nBuilding executable (onedir mode)...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",
        "--windowed",
        "--noupx",
        "--name", APP_NAME,
        "--collect-submodules", "src",
    ]
    # --version-file embeds Windows VERSIONINFO; only valid on Windows builds.
    if sys.platform == "win32" and (ROOT / "version_info.txt").exists():
        cmd += ["--version-file", "version_info.txt"]
    cmd.append(ENTRY)
    _run(cmd)

    exe_name = f"{APP_NAME}.exe" if sys.platform == "win32" else APP_NAME
    out = ROOT / "dist" / APP_NAME / exe_name
    if not out.exists():
        print(f"\nERROR: build did not produce {out}", file=sys.stderr)
        sys.exit(1)

    print(f"\nOK: {out}")
    print(f"Distribute the whole 'dist/{APP_NAME}/' folder (zipped), not just the binary.")


if __name__ == "__main__":
    main()
