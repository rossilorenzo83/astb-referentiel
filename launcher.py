"""Entry point for PyInstaller: keeps src/ as a proper package so relative imports work."""
from src.main import main

if __name__ == "__main__":
    main()
