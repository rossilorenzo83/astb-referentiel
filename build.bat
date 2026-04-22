@echo off
cd /d "%~dp0"

echo Installation des dependances...
pip install -r requirements.txt pyinstaller

echo.
echo Nettoyage des builds precedents...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist ASTB_Annuaire.spec del /q ASTB_Annuaire.spec

echo.
echo Construction de l'executable...
pyinstaller --onefile --windowed --name ASTB_Annuaire ^
    --collect-submodules src ^
    launcher.py

echo.
if exist dist\ASTB_Annuaire.exe (
    echo OK : dist\ASTB_Annuaire.exe
) else (
    echo ERREUR : l'executable n'a pas ete genere.
)
pause
