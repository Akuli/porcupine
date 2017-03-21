# Porcupine

This is a simple and easy-to-use editor for writing Python code. You
need Python 3.3 or newer with Tkinter to run this.

![Screenshot.](screenshot.png)

This editor has everything that a Python editor needs:

- Syntax highlighting with different color themes
- Converting tabs to spaces
- Automatic indenting
- Indent/dedent block with Tab and Shift+Tab
- Stripping trailing whitespace
- Line numbers
- Line length marker
- Simple all-words-in-file autocompleting with tab
- Multiple files can be opened at the same time like pages in a web browser
- Status bar that shows current line and column numbers
- Simple and easy-to-use setting dialog
- PEP-8 compatible default settings

These features will be added later: 

- Something that runs the file in a terminal or PowerShell

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
