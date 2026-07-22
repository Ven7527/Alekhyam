import os
import sys
sys.path.insert(0, os.path.abspath(".."))

project   = "Alekhyam"
author    = "Ven7527"
release   = "0.0.1"
copyright = "2025, Ven7527"

extensions = [
    "sphinx.ext.autosectionlabel",
]

templates_path   = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme        = "furo"
html_title        = "Alekhyam documentation"
html_static_path  = ["_static"]
html_logo         = None

html_theme_options = {
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
}

autosectionlabel_prefix_document = True
