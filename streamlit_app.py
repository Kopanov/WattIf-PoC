"""Root entry point for hosted deployment (Replit / Hugging Face Spaces).

Adds ``src`` to the path and runs the real UI, so hosts that expect a top-level
``streamlit_app.py`` work without installing the package. Run locally with:

    streamlit run streamlit_app.py
"""
import os
import sys
import runpy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

runpy.run_path(
    os.path.join(os.path.dirname(__file__), "src", "whatif", "ui", "streamlit_app.py"),
    run_name="__main__",
)
