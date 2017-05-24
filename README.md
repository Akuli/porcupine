# Porcupine

Porcupine is a simple and beginner-friendly editor for writing Python
code. If you ever used anything like Notepad, Microsoft Word or
LibreOffice Writer before, you will feel right at home. All features of
Porcupine should work great on Windows, Linux and Mac OSX.

![Screenshot.](screenshot.png)

This editor has everything that a Python editor needs:

- Syntax highlighting with different color themes
- Running files in a terminal or command prompt by pressing F5
- Converting tabs to spaces
- Simple all-words-in-file autocompleting with tab
- Automatic indenting and stripping trailing whitespace when pressing Enter
- Indent/dedent block with Tab and Shift+Tab
- Line numbers
- Line length marker
- Find/replace
- Simple and easy-to-use setting dialog
- PEP-8 compatible default settings
- Multiple files can be opened at the same time like pages in a web browser
- Status bar that shows current line and column numbers
- Powerful plugin interface

[comment]: # (TODO: plugin docs and a link to them here)

## Installing Porcupine

There are detailed installation instructions in [the Porcupine
Wiki](https://github.com/Akuli/porcupine/wiki/Installing-Porcupine).
Here's a summary of the commands for inpatient people :)

### Windows

    py -m pip install --user https://github.com/Akuli/porcupine/archive/master.zip
    pyw -m porcupine

### Other operating systems

    python3 -m pip install --user https://github.com/Akuli/porcupine/archive/master.zip
    python3 -m porcupine &
