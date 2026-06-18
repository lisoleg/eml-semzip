"""Default constants and custom exceptions for eml_semzip.

This module is a leaf dependency (no imports from other package modules)
to avoid circular imports.
"""

# ---------------------------------------------------------------------------
# Compression defaults
# ---------------------------------------------------------------------------
DEFAULT_THETA_DEAD: float = 0.45
DEFAULT_KEEP_RATIO: float = 0.15

# ---------------------------------------------------------------------------
# SemPkt binary format
# ---------------------------------------------------------------------------
SEMPKT_MAGIC: bytes = b"ESZP"
SEMPKT_VERSION: int = 1

# ---------------------------------------------------------------------------
# Numerical tolerances
# ---------------------------------------------------------------------------
I_VALUE_EPSILON: float = 1e-9
I_VALUE_TOLERANCE: float = 1e-6
DSEM_TOLERANCE: float = 1e-4

# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------
MAX_CYCLE_DEPTH: int = 100

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------
EXIT_SUCCESS: int = 0
EXIT_ARG_ERROR: int = 1
EXIT_FORMAT_ERROR: int = 2
EXIT_KB_SIG_ERROR: int = 3
EXIT_KB_MISSING: int = 4


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------
class EMLSemZipError(Exception):
    """Base exception for all eml_semzip errors."""


class FileFormatError(EMLSemZipError):
    """Raised when a file format is invalid or corrupted."""


class KBSignatureError(EMLSemZipError):
    """Raised when KB signature verification fails."""


class KBMissingError(EMLSemZipError):
    """Raised when a required KB is not available."""
