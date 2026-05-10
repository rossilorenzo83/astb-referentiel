@echo off
cd /d "%~dp0"

echo Installing dependencies...
pip install -r requirements.txt pyinstaller

echo.
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist ASTB_Annuaire.spec del /q ASTB_Annuaire.spec

echo.
echo Building executable (onedir mode, fewer antivirus false positives)...
pyinstaller --onedir --windowed --noupx --name ASTB_Annuaire ^
    --version-file version_info.txt ^
    --collect-submodules src ^
    launcher.py

echo.
if exist dist\ASTB_Annuaire\ASTB_Annuaire.exe (
    echo OK: dist\ASTB_Annuaire\ASTB_Annuaire.exe
    echo Distribute the entire 'dist\ASTB_Annuaire' folder ^(zipped^), not just the .exe.
) else (
    echo ERROR: executable was not generated.
)
pause
