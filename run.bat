@echo off
cd /d "%~dp0"
python -m src.main
if errorlevel 1 (
    echo.
    echo Une erreur est survenue. Verifiez que Python est installe.
    pause
)
