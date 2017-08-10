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

    py -m pip install --user http://goo.gl/SnlfHw
    pyw -m porcupine

### Other operating systems

    python3 -m pip install --user http://goo.gl/SnlfHw
    python3 -m porcupine &

## FAQ

### Why not use editor X?

Because Porcupine is better.

### Is Porcupine based on IDLE?

Of course not. IDLE is an awful mess that you should stay far away from.

### Why did you create a new editor?

Because I can.

### Why did you create a new editor in tkinter?

Because I can.

### How does feature X work?

See [porcupine/plugins/](porcupine/plugins/)X.py.

### I want an editor that does X, but X is not in the feature list above. Does Porcupine do X?

It probably doesn't, but [it's easy to write a
plugin](https://akuli.github.io/porcupine/plugin-intro.html) if you know how to
use tkinter. If you don't, you can [create an issue on
GitHub](https://github.com/Akuli/porcupine/issues/new) and I *may* write the
plugin for you if I feel like it.

### Help! Porcupine doesn't work.

Please [update Porcupine](https://github.com/Akuli/porcupine/wiki/Installing-and-Running-Porcupine#updating-porcupine).
If it still doesn't work, [let me know by creating an issue on
GitHub](http://github.com/Akuli/porcupine/issues/new).
