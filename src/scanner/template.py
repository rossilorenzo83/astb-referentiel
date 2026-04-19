"""Data structures describing a file's inferred layout."""

from dataclasses import dataclass, field
from enum import Enum, auto


class FileFormat(Enum):
    EXCEL = auto()
    WORD = auto()


class LayoutType(Enum):
    SINGLE_COLUMN_STATEFUL = auto()
    TABULAR = auto()
    PARAGRAPH_SECTIONED = auto()
    PARAGRAPH_FREETEXT = auto()


class SectionDetectorKind(Enum):
    SHEET_NAME = auto()
    NUMBERED_PREFIX = auto()
    STYLE_BASED = auto()
    BOLD_OR_HEADING = auto()
    REGEX_PATTERN = auto()


@dataclass
class FieldMapping:
    doctor_field: str
    source_label: str
    column_index: int | None = None
    label_regex: str | None = None


@dataclass
class SectionDetector:
    kind: SectionDetectorKind
    level: str
    pattern: str = ""
    sheet_scope: bool = False


@dataclass
class HeaderBlock:
    row_count: int = 0
    city_row: int | None = None
    type_centre_row: int | None = None
    responsable_row: int | None = None
    responsable_pattern: str = ""


@dataclass
class SheetTemplate:
    name: str = ""
    layout: LayoutType = LayoutType.SINGLE_COLUMN_STATEFUL
    header: HeaderBlock | None = None
    field_mappings: list[FieldMapping] = field(default_factory=list)
    section_detectors: list[SectionDetector] = field(default_factory=list)
    has_multi_names: bool = False
    has_idem_references: bool = False
    data_start_row: int = 0
    column_count: int = 1


@dataclass
class FileTemplate:
    file_format: FileFormat = FileFormat.EXCEL
    path: str = ""
    sheets: list[SheetTemplate] = field(default_factory=list)
    scan_warnings: list[str] = field(default_factory=list)
