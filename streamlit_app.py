"""Root entry point for hosted deployment (Replit / Hugging Face Spaces).

Adds ``src`` to the path and runs the real UI, so hosts that expect a top-level
``streamlit_app.py`` work without installing the package. Run locally with:

    streamlit run streamlit_app.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from whatif.ui import streamlit_app  # noqa: E402,F401  (importing runs the Streamlit app)
