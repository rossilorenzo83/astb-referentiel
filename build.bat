@echo off
echo Installation des dependances...
pip install -r requirements.txt pyinstaller

echo.
echo Construction de l'executable...
pyinstaller --onefile --windowed --name ASTB_Annuaire --add-data "resources;resources" src\main.py

echo.
echo L'executable se trouve dans le dossier dist\
pause
