"""WattIf — descriptive-only what-if scenario simulator.

PoC for ODEON Open Call #1, Challenge 10. Keep this module light: importing ``whatif``
must not pull in heavy optional dependencies (pvlib, streamlit, torch, ...). Submodules
import those lazily inside the functions that need them.
"""
from __future__ import annotations

__version__ = "2026.6.5"  # CalVer (YYYY.M.D)
__all__ = ["__version__"]
