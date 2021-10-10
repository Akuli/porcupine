import importlib
import inspect
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(".."))
import porcupine

sys.path.insert(0, os.path.abspath("."))
extensions = [
    "sphinx.ext.intersphinx",
    "sphinx.ext.coverage",
    "sphinx.ext.linkcode",
    "sphinx.ext.githubpages",
    "sphinx.ext.autodoc",
    "extensions",  # my extensions.py
]

source_suffix = ".rst"

master_doc = "index"

project = "Porcupine API"
copyright = porcupine.__copyright__.split("(c)")[1]
author = "Akuli"

nitpicky = False

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
version = porcupine.__version__
release = porcupine.__version__

language = None
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
pygments_style = "sphinx"


html_theme = "alabaster"

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
# html_theme_options = {}

html_static_path = ["_static"]

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}


def linkcode_resolve(domain, info):
    if domain != "py" or not info["module"] or not info["module"].startswith("porcupine."):
        return None

    project_root = Path(__file__).absolute().parent.parent

    assert info.keys() == {"module", "fullname"}
    try:
        objekt = importlib.import_module(info["module"])
        for part in info["fullname"].split("."):
            objekt = getattr(objekt, part)
        path = Path(inspect.getsourcefile(objekt))
        lines, first_lineno = inspect.getsourcelines(objekt)
    except (AttributeError, TypeError):
        return None

    if project_root not in path.parents:
        return None

    assert path.is_file()
    last_lineno = first_lineno + len(lines) - 1
    path_string = path.relative_to(project_root).as_posix()
    commit = subprocess.check_output("git rev-parse HEAD", shell=True).strip().decode("ascii")
    return f"https://github.com/Akuli/porcupine/blob/{commit}/{path_string}#L{first_lineno}-L{last_lineno}"
