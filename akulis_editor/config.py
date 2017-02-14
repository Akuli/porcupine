# Copyright (c) 2017 Akuli

# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:

# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""The Python configuration file.

Some people seem to think that Python configuration files are a bad
idea, but they are after all something that all Python programmers
understand. It can't be too bad because Sphinx does it :)
"""

import os


CONFIGFILE = os.path.join(os.path.expanduser('~'), '.akulis-editor.py')

DEFAULT_CONFIG = '''
# This is an automatically generated setting file for Akuli's Editor.
# The file is executed in Python with exec(). Feel free to edit this to
# customize how the editor looks and behaves.

# The encoding of all opened and saved files.
encoding = 'UTF-8'
# Add a trailing newlines to ends of files when saving?
add_trailing_newline = True

# Use these to customize how the editor looks. The color values can be
# any Tkinter colors, including some common color names and '#RRGGBB'
# strings.
colors = {
    'foreground': 'white',
    'background': 'black',
    'string': 'yellow',
    'keyword': 'cyan',
    'exception': 'red',
    'builtin': 'mediumpurple',
    'comment': 'gray',
    'decorator': 'violetred',
}

# The editor's Tkinter font. Example: 'courier 12 bold'.
font = 'TkFixedFont'
# How many spaces to insert when tab is pressed? 0 means tabs instead
# of spaces.
indent = 4
# How many undo/redo moves to remember? 0 means that there is no limit.
maxundo = 0
# Display the cursor as a square-shaped block instead of a vertical line?
blockcursor = False
# Display line numbers?
linenumbers = True

# Add buttons for things in the File menu?
topbar = True
# Display the current line, column and some other things at the bottom?
statusbar = True
# The default window size as a tkinter geometry. For example, 700x400
# means 700 pixels wide and 400 pixels high.
default_geometry = '650x500'
'''.strip()


def load():
    namespace = {}
    exec(DEFAULT_CONFIG, namespace)
    try:
        with open(CONFIGFILE, 'r') as f:
            code = f.read()
    except FileNotFoundError:
        print("%s: setting file was not found, creating default "
              "setting file" % __name__)
        with open(CONFIGFILE, 'w') as f:
            print(DEFAULT_CONFIG, file=f)
    else:
        exec(code, namespace)
    return namespace
