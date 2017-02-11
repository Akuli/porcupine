#!/usr/bin/env python3

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

"""This is a really simple text editor for writing Python code.

If you have used something like Notepad, Microsoft Word or LibreOffice
Write before you know how to use this editor. Just make sure you have
Python 3.2 or newer with Tkinter installed and run this.
"""

import argparse
import configparser
import os

from .editor import EditorWindow


CONFIGFILE = os.path.join(os.path.expanduser('~'), '.akulis-editor.ini')

DEFAULT_CONFIG = '''\
# This is an automatically generated configuration file for Akuli's Editor.
[files]
# The encoding of opened files. Set this to UTF-8 unless you know that
# you need something else.
encoding = UTF-8
# Add a trailing newline to the files? This is recommended.
trailing-newline = yes

# Use these to customize how the editor looks.
[colors]
foreground = white
background = black
string = yellow
keyword = cyan
exception = red
builtin = mediumpurple
comment = gray

# These are used with syntax highlighting.
[regexes]
identifier = \\b%s\\b
comment = #.*$
string = '[^']*[^\\\\]'|"[^"]*[^\\\\]"
multiline-string = """[\\S\\s]*?"""|\'\'\'[\\S\\s]*?\'\'\'

[editing]
# How many spaces to insert when tab is pressed? 0 means tabs instead of
# spaces. Set this to 4 unless you need something else.
indent = 4
# How many undo/redo moves to remember? 0 means that there is no limit.
maxundo = 0
# Display the cursor as a square-shaped block instead of a vertical
# line?
blockcursor = no

[toolbars]
# Add buttons for things in the File menu?
topbar = yes
# Display the current line, column and some other things at the bottom?
statusbar = yes
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'file', nargs=argparse.OPTIONAL,
        help="open this file when the editor starts")
    parser.add_argument(
        '-d', '--default-config', action='store_true',
        help="create a default ~/.akulis-editor.ini")
    args = parser.parse_args()
    if args.default_config:
        if os.path.exists(CONFIGFILE):
            answer = input("The configuration file exists. Overwrite? [Y/n] ")
            if answer not in {'Y', 'y'}:
                print("Interrupt.")
                return
        with open(CONFIGFILE, 'w', encoding='utf-8') as f:
            f.write(DEFAULT_CONFIG)
        print("Default configuration was written to %s."
              % CONFIGFILE)
        return

    settings = configparser.ConfigParser(interpolation=None)
    settings.read_string(DEFAULT_CONFIG)
    settings.read([CONFIGFILE])

    editor = EditorWindow(settings)
    editor.title("Akuli's Editor")
    if args.file is not None:
        editor.open_file(args.file)
    editor.mainloop()


if __name__ == '__main__':
    try:
        import faulthandler
        faulthandler.enable()
    except ImportError:
        pass
    main()
