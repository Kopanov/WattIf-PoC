"""WattIf — descriptive-only what-if scenario simulator.

PoC for ODEON Open Call #1, Challenge 10. Keep this module light: importing ``whatif``
must not pull in heavy optional dependencies (pvlib, streamlit, torch, ...). Submodules
import those lazily inside the functions that need them.
"""
from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
