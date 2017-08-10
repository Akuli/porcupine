"""Python autocompletion with Jedi.

You need jedi if you want to use this module. Install it like this on
Windows::

    py -m pip install --user jedi

Or like this on other operating systems::

    python3 -m pip install --user jedi
"""

import logging
from porcupine.plugins import autocomplete

try:
    import jedi
except ImportError:
    logging.getLogger(__name__).exception("jedi is not installed")
    jedi = None


def jedi_completer(source, line, column):
    script = jedi.Script(source, line, column)
    return (c.complete for c in script.completions())


def setup():
    if jedi is not None:
        autocomplete.register_completer("Python", jedi_completer)
