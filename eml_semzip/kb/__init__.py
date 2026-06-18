"""KB subpackage: EMLLiteKB and built-in KB factories."""

from .eml_lite_kb import EMLLiteKB, AbsorbRecord
from .builtin_kb import create_empty_kb, create_builtin_kb

__all__ = ["EMLLiteKB", "AbsorbRecord", "create_empty_kb", "create_builtin_kb"]
