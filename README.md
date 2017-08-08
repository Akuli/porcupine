# Porcupine

Porcupine is a simple and beginner-friendly editor. If you ever used anything
like Notepad, Microsoft Word or LibreOffice Writer before, you will feel right
at home. All features of Porcupine should work great on Windows, Linux and Mac
OSX.

![Screenshot.](screenshot.png)

Here's a list of the most important features:

- Syntax highlighting with Pygments (supports many programming languages and
  color themes)
- Filetype specific settings, including optional tabs to spaces conversion
- Simple all-words-in-file autocompleting with tab
- Automatic indenting and trailing whitespace stripping when pressing Enter
- Indent/dedent block with Tab and Shift+Tab
- Line numbers
- Line length marker
- Find/replace
- Simple and easy-to-use setting dialog
- Multiple files can be opened at the same time like pages in a web browser
- Status bar that shows current line and column numbers
- [Very powerful plugin API](https://akuli.github.io/porcupine/)

Currently there are also a few Python specific features:

- Running Python files in a terminal or command prompt by pressing F5
- PEP-8 compatible Python settings

## Installing Porcupine

There are detailed installation instructions in [the Porcupine
Wiki](https://github.com/Akuli/porcupine/wiki/Installing-and-Running-Porcupine).
Here's a summary of the commands for inpatient people :)

### Windows

    py -m pip install --user https://github.com/Akuli/porcupine/archive/master.zip
    pyw -m porcupine

### Other operating systems

    python3 -m pip install --user https://github.com/Akuli/porcupine/archive/master.zip
    python3 -m porcupine &
