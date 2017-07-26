# this docstring doesn't contain a one-line summary because editor.py
# uses it as a welcome message
"""
Porcupine is a simple, beginner-friendly editor for writing Python code.
If you ever used anything like Notepad, Microsoft Word or LibreOffice
Writer before, you will feel right at home.

You can create a new file by pressing Ctrl+N or open an existing file by
pressing Ctrl+O. The file name will be displayed in red if the file has
been changed and you can save the file with Ctrl+S. Then you can run the
file by pressing F5.

See the menus at the top of the editor for other things you can do and
their keyboard shortcuts.
"""

version_info = (0, 20, 0)        # this is updated with bump.py
__version__ = '%d.%d.%d' % version_info
__author__ = 'Akuli'
__copyright__ = 'Copyright (c) 2017 Akuli'
