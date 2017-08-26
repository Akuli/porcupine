# Porcupine

Porcupine is a simple and beginner-friendly editor. If you ever used anything
like Notepad, Microsoft Word or LibreOffice Writer before, you will feel right
at home. All features of Porcupine should work great on Windows, Linux and Mac
OSX.

![Screenshot.](screenshot.png)

Here's a list of the most important features:

- Syntax highlighting with [Pygments][] (supports many programming languages and
  color themes, and is easily extensible)
- Filetype specific settings, including optional tabs to spaces conversion
- Simple all-words-in-file autocompleting with tab
- Automatic indenting and trailing whitespace stripping when pressing Enter
- Indent/dedent block with Tab and Shift+Tab
- Line numbers
- Line length marker
- Find/replace
- Simple and easy-to-use setting dialog
- Multiple files can be opened at the same time like tabs in a web browser
- Split view for tabs
- Status bar that shows current line and column numbers
- [Very powerful plugin API](https://akuli.github.io/porcupine/)

Currently there are also a few Python specific features:

- Running Python files in a terminal or command prompt by pressing F5
- PEP-8 compatible Python settings

[Pygments]: http://pygments.org/

## Installing Porcupine

There are detailed installation instructions in [the Porcupine
Wiki](https://github.com/Akuli/porcupine/wiki/Installing-and-Running-Porcupine).
Here's a summary of the commands for inpatient people :)

Make sure you have Python 3.4 or newer installed, and run these commands
on a command prompt, PowerShell or terminal:

### Windows

    py -m pip install --user http://goo.gl/SnlfHw
    pyw -m porcupine

### Other operating systems

    python3 -m pip install --user http://goo.gl/SnlfHw
    python3 -m porcupine &

## FAQ

### Help! Porcupine doesn't work.
Please [update Porcupine](https://github.com/Akuli/porcupine/wiki/Installing-and-Running-Porcupine#updating-porcupine).
If it still doesn't work, [let me know by creating an issue on
GitHub](http://github.com/Akuli/porcupine/issues/new).

### Why not use editor X?
Because Porcupine is better.

### Is Porcupine based on IDLE?
Of course not. IDLE is an awful mess that you should stay far away from.

### Why did you create a new editor?
Because I can.

### Why did you create a new editor in tkinter?
Because I can.

### How does feature X work?
See [porcupine/](porcupine/)X.py or [porcupine/plugins/](porcupine/plugins/)X.py.

### I want an editor that does X, but X is not in the feature list above. Does Porcupine do X?
Maybe it can. See [the more_plugins directory](more_plugins/).

If you don't find what you are looking for you can [write your own
plugin](https://akuli.github.io/porcupine/plugin-intro.html) if you know
how to use tkinter. If you don't, you can [create an issue on
GitHub](https://github.com/Akuli/porcupine/issues/new) and I *may* write
the plugin for you if I feel like it.

### Can I play tetris with Porcupine?
Yes. See [more_plugins](more_plugins/).

### Is Porcupine an Emacs?
Not by default, but you can [install more plugins](more_plugins/).
