# Porcupine

Porcupine is an editor written with the notorious Tkinter library. It supports
most things you would expect from an editor, such as autocompletions and syntax
highlighting.

![Screenshot.](screenshot.png)

Most important features:
- Syntax highlighting with [Pygments][] (supports many programming languages
  and color themes, extensible)
- Autocompletions when pressing tab
- Jump to definition with Ctrl+click
- [Langserver] support
- [Editorconfig][] support
- Git support
- Compiling files inside the editor window
- Running files in a separate terminal or command prompt window
- Automatic indenting and trailing whitespace stripping when Enter is pressed
- Indent/dedent block with Tab and Shift+Tab
- Commenting/uncommenting multiple lines by selecting them and typing a #
- Highlighting matching parentheses
- Line numbers
- Line length marker
- Find/replace
- Code folding
- Multiple files can be opened at the same time like tabs in a web browser
- The tabs can be dragged out of the window to open a new Porcupine window conveniently

[Pygments]: https://pygments.org/
[Langserver]: https://langserver.org/
[Editorconfig]: https://editorconfig.org/

Porcupine also has [a very powerful plugin
API](https://akuli.github.io/porcupine/), and most of the above features are
implemented as plugins. This means that if you know how to use Python 3 and
tkinter, you can easily customize your editor to do anything you want to. In
fact, the plugin API is so powerful that if you run Porcupine without plugins,
it shows up as an empty window.

## Installing Porcupine

### Development Install

See [CONTRIBUTING.md](CONTRIBUTING.md) for development instructions.

### Debian-based Linux distributions (e.g. Ubuntu, Mint)

Open a terminal and run these commands:

    sudo apt install python3-tk python3-pip
    sudo apt install --no-install-recommends tkdnd    # for drop_to_open plugin
    python3 -m pip install --user --upgrade pip wheel
    python3 -m venv porcupine-venv
    source porcupine-venv/bin/activate
    python3 -m pip install https://github.com/Akuli/porcupine/archive/v2022.08.28.zip
    porcu

If you want to leave Porcupine running and use the same terminal for something else,
you can use `porcu&` instead of `porcu`.
To run porcupine later, you need to activate the virtualenv before running it:

    source porcupine-venv/bin/activate
    porcu

You can uninstall Porcupine by deleting `porcupine-venv`.

### Other Linux distributions

Install Python 3.7 or newer with pip and tkinter somehow.
If you want drag and drop support, also install tkdnd for the Tcl interpreter that tkinter uses.
Then run these commands:

    python3 -m pip install --user --upgrade pip wheel
    python3 -m venv porcupine-venv
    source porcupine-venv/bin/activate
    python3 -m pip install https://github.com/Akuli/porcupine/archive/v2022.08.28.zip
    porcu

If you want to leave Porcupine running and use the same terminal for something else,
you can use `porcu&` instead of `porcu`.
To run porcupine later, you need to activate the virtualenv before running it:

    source porcupine-venv/bin/activate
    porcu

You can uninstall Porcupine by deleting `porcupine-venv`.

### MacOS

I don't have a Mac. If you have a Mac, you can help me a lot by installing
Porcupine and letting me know how well it works.

I think you can download Python with tkinter from
[python.org](https://www.python.org/) and then run the commands for
"other Linux distributions" above.

### Windows

Download a Porcupine installer from [the releases page](https://github.com/Akuli/porcupine/releases) and run it.
Because I haven't asked Microsoft to trust Porcupine installers,
you will likely get a warning similar to this one:

![Windows thinks it protected your PC](windows-defender.png)

You should still be able to run the installer by clicking "More info".
When installed, you will find Porcupine from the start menu.

## FAQ

### What's new in the latest Porcupine release?

See [CHANGELOG.md](CHANGELOG.md).

### Does Porcupine support programming language X?
You will likely get syntax highlighting without any configuring
and autocompletions with a few lines of configuration file editing.
See [the instructions on Porcupine wiki](https://github.com/Akuli/porcupine/wiki/Getting-Porcupine-to-work-with-a-programming-language).

### Help! Porcupine doesn't work.
Please install the latest version.
If it still doesn't work, [let me know by creating an issue on
GitHub](http://github.com/Akuli/porcupine/issues/new).

### Is Porcupine written in Porcupine?

Yes. I wrote the very first version in `nano`, but Porcupine has changed a lot since.

### Why is it named Porcupine?

I think because I didn't find other projects named porcupine, but I don't remember exactly.
Originally, Porcupine was named "Akuli's Editor".

### I want an editor that does X, but X is not in the feature list above. Does Porcupine do X?
Maybe it can, see [the more_plugins directory](more_plugins/). If you don't
find what you are looking for, you can write your own plugin, or alternatively,
you can [create an issue on GitHub](https://github.com/Akuli/porcupine/issues/new)
and hope that I feel like writing the plugin for you.

### Why did you create a new editor?
Because I can.

### Why did you create a new editor in tkinter?
Because I can.

### How does feature X work?
See [porcupine/](porcupine/)X.py or [porcupine/plugins/](porcupine/plugins/)X.py.

### Why not use editor X?
Because Porcupine is better.

### Is Porcupine based on IDLE?
Of course not. IDLE is an awful mess that you should stay far away from.

### Is Porcupine a toy project or is it meant to be a serious editor?
Porcupine is meant to be a serious editor, in fact you might regret even touching it.
https://www.youtube.com/watch?v=Y3iUoFkDKjU
