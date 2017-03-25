# Porcupine

This is a simple and easy-to-use editor for writing Python code. You
need Python 3.3 or newer with Tkinter to run this. All features of
Porcupine work great on Windows and Linux.

If you have a Mac and Porcupine's "Run this file" button works or
doesn't work on it, please let me know. I don't have an up-to-date Mac,
so the Mac code in [porcupine/terminal.py](porcupine/terminal.py) is
completely untested and I have no idea if it works.

![Screenshot.](screenshot.png)

This editor has everything that a Python editor needs:

- Syntax highlighting with different color themes
- Running files in a terminal or command prompt by pressing F5
- Converting tabs to spaces
- PEP-8 compatible default settings
- Simple all-words-in-file autocompleting with tab
- Automatic indenting and stripping trailing whitespace when pressing Enter
- Indent/dedent block with Tab and Shift+Tab
- Line numbers
- Line length marker
- Multiple files can be opened at the same time like pages in a web browser
- Status status bar that shows current line and column numbers
- Simple and easy-to-use setting dialog

## How do I run this thing?

Make sure you have Python 3.3 or newer with tkinter installed. Tkinter
comes with Python for Windows and OSX, but you need to install it
yourself on most Linux distributions. For example, you can do this on
Debian-based distributions (Ubuntu, Linux Mint, etc.):

    $ sudo apt install python3-tk

Then you can download Porcupine, `cd` to where you downloaded it and run
it with Python's `-m` option. Fore example, it might look like this if
you use Git for downloading Porcupine:

    $ git clone https://github.com/Akuli/porcupine
    $ cd porcupine
    $ python3 -m porcupine
