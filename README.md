# Porcupine

This is a simple and easy-to-use editor for writing Python code. You
need Python 3.3 or newer with Tkinter to run this.

![Screenshot.](screenshot.png)

This editor supports everything that an editor needs to support:

- Syntax highlighting with different color themes
- Converting tabs to spaces
- Automatic indenting and indent/dedent block with tab and shift+tab
- Stripping trailing whitespace
- Simple autocompleting with tab
- Status bar that shows current line and column numbers
- Multiple files can be opened at the same time in separate tabs
- Line numbers
- Simple setting dialog

These features will be added later: 

- Line length marker
- Something that runs the file in a terminal or PowerShell

## How do I run this thing?

Make sure you have Python 3.3 or newer with tkinter installed. Tkinter
comes with Python for Windows and OSX, but you need to install it
yourself on most Linux distributions. For example, you can do this on
Debian-based distributions (Ubuntu, Linux Mint, etc.):

    $ sudo apt install python3-tk

Then you can download Porcupine, `cd` to where you downloaded it and run
it with Python's `-m` option. Fore example, like this:

    $ git clone https://github.com/Akuli/porcupine
    $ cd porcupine
    $ python3 -m porcupine
