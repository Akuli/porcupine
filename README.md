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

## How do I run this thing?

Porcupine requires Python 3.3 or newer with tkinter. If you [installed
Python](https://github.com/Akuli/python-tutorial/blob/master/basics/installing-python.md)
yourself it probably came with tkinter, but most Linux distributions
don't include it so you need to install tkinter yourself. For example,
you can run this command on a terminal on Debian-based Linux
distributions (Ubuntu, Mint etc.):

    sudo apt install python3-tk

Then you can download Porcupine. You can download it with Git...

    git clone https://github.com/Akuli/porcupine
    cd porcupine

...or if you don't have Git, you can do this instead:

1. Go [here](https://github.com/Akuli/porcupine) if you aren't here
   already.
2. Click the big green "Clone or download" button in the top right of
   the page, then click "Download ZIP".
3. Open the ZIP you downloaded and drag and drop `porcupine-master` to
   your desktop.
4. Open a PowerShell, command prompt or terminal and go to the folder
   you downloaded. Like this:

        cd Desktop
        cd porcupine-master

Now we can run porcupine. Run this if you're using Windows:

    py -m porcupine

Use this command instead on Mac OSX and Linux:

    python3 -m porcupine
