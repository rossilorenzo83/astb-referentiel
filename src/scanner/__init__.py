"""Scanner: dynamically infer file structure, then parse with the inferred template."""

from .scan_excel import scan_excel
from .scan_word import scan_word
from .generic_parser import parse_with_template


def scan_and_parse(path: str) -> tuple[list, list[str]]:
    """Scan a file to detect its structure, then parse using the inferred template."""
    ext = path.rsplit(".", 1)[-1].lower()

    if ext in ("xlsx", "xls"):
        template, buffer = scan_excel(path)
    elif ext == "docx":
        template, buffer = scan_word(path)
    else:
        return [], [f"Format non reconnu: .{ext}"]

    return parse_with_template(template, buffer)
