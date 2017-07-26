"""Editing and cursor behaviour related plugins.

Each of the plugins in this subpackage could be moved outside of this
package too and used independently if you add a simple setup() function,
and they're all in this package just to make them easier to find.
"""

from . import autoindent, rstrip, tabs2spaces

# TODO: this sucks, but porcupine._pluginloader supports no kind of
# setup_before thing that other plugins could use :(
setup_after = ['autocomplete', 'indent_block']


def setup(editor):
    # the order of some of these things matters, see the docstrings in
    # other files for more info
    autoindent.setup(editor)
    rstrip.setup(editor)
    tabs2spaces.setup(editor)
