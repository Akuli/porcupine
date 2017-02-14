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

"""Run the editor."""

import argparse
import os

from . import config
from .editor import Editor


def main():
    # TODO: allow multiple file args when we have multiple tabs
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'file', nargs=argparse.OPTIONAL,
        help="open this file when the editor starts")
    args = parser.parse_args()

    settings = config.load()
    editor = Editor(settings)
    if args.file is not None:
        # the editor doesn't create new files when opening, so we need to
        # take care of that here
        if os.path.exists(args.file):
            editor.open_file(args.file)
        else:
            editor.filename = args.file
    editor.mainloop()


if __name__ == '__main__':
    main()
