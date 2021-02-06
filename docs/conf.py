import os
import sys

sys.path.insert(0, os.path.abspath('..'))
import porcupine

sys.path.insert(0, os.path.abspath('.'))
extensions = [
    'sphinx.ext.intersphinx',
    'sphinx.ext.coverage',
    'sphinx.ext.viewcode',
    'sphinx.ext.githubpages',
    'sphinx.ext.autodoc',
    'extensions',       # my extensions.py
]

source_suffix = '.rst'

master_doc = 'index'

project = 'Porcupine API'
copyright = porcupine.__copyright__.split('(c)')[1]
author = 'Akuli'

nitpicky = False

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
version = porcupine.__version__
release = porcupine.__version__

language = None
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
pygments_style = 'sphinx'


html_theme = 'alabaster'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
# html_theme_options = {}

html_static_path = ['_static']

intersphinx_mapping = {'python': ('https://docs.python.org/3', None)}
