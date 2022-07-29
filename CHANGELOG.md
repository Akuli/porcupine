Unlike the Git commit history, this changelog does not include code cleanups
and other details that don't affect using Porcupine.


## Unreleased

Windows improvements:
- Porcupine no longer looks blurry on some Windows installs. Thank you [VideoCarp](https://github.com/VideoCarp/) for finally fixing this old issue!
- Alt+F4 now works on Windows. Previously it worked on some Windows systems and didn't work on others.

Directory tree:
- There are a couple new options that appear when right-clicking: "Copy full path to clipboard" and "New directory here". Thank you [ihammadasghar](https://github.com/ihammadasghar) and [TyGuy54](https://github.com/TyGuy54).
- Items in the directory tree are indented less than before. This makes the directory tree fit in a narrow area when there are many nested directories.
- Some keyboards have a Menu key (also known as App key) that usually does the same thing as right-clicking. This now works in the directory tree.
- The directory tree runs `git status` internally to figure out how to color each item (green means your changes will be included in the next commit, for example). It no longer kills `git` if it doesn't complete within a few seconds. This prevents lock file errors that happened when trying to run `git` afterwards.

Pastebin menu:
- When you pastebin for the first time, you now get a dialog asking whether you really wanted to do it. In other words, you can no longer accidentally send your code to a pastebin service.
- Indentations are now removed when pastebinning. Previously indentation was removed only from the first line of code when pastebinning to dpaste.com. This was annoying when pastebinning a part from the middle of a function, for example. (If you select some text before pastebinning, only the selected text is pastebinned.)

Running programs without an external terminal window:
- Porcupine no longer freezes if the program produces a lot of output, e.g. `print` inside an infinite loop.
- On Linux and MacOS, there is now a pause button that can be used to stop and continue running the program. This is useful if you made a game but you didn't implement pause yet, for example. Thank you [rdbende](https://github.com/rdbende) for implementing this.
- Porcupine no longer stops showing the output in a corner case. This corner case happened frequently when printing large amounts of random bytes in Python.
- Porcupine now recognizes file names and line numbers of the form `(filename:linenumber)` and makes them clickable. At least valgrind prints source code locations this way.

Other new features and improvements:
- You can now decide whether Porcupine should remember your opened tabs when you close and reopen it. There's a new checkbox in *Porcupine Settings* (in the *Settings* menu).
- You can now select text and press Ctrl+G to search the selected text on Google. This is useful if you don't know what a function does, for example. Thank you [okankamilsen](https://github.com/okankamilsen) for implementing this.
- Hover popups now appear with some delay: if you move your mouse over a function call, you will now have to wait about half a second before you see a description of what the function does. This makes the hover popups less annoying and reduces CPU usage when moving the mouse. Thank you [rdbende](https://github.com/rdbende) for implementing this.
- The color scheme buttons in Porcupine Settings can now be accessed with keyboard in addition to clicking them.
- It is no longer possible to open several instances of the same dialog. For example, previously it was possible to open Plugin Manager even if Plugin Manager was already opened. Thank you [rdbende](https://github.com/rdbende) for fixing this.
- The encoding button (at bottom right, usually displaying `utf-8`) now becomes wider if you select an encoding with a long name. Thank you [rdbende](https://github.com/rdbende) and [Moosems](https://github.com/Moosems).

Removed features:
- It is no longer possible to use langservers with local TCP sockets. Use stdio (i.e. stdin and stdout) instead. So far I haven't seen any langservers that can't be used with stdio.


## v0.99.2

Directory tree:
- When a file has been renamed, it is now selected. Previously you would have to click the file after renaming it if you wanted to open it, for example. Thank you [rdbende](https://github.com/rdbende) for fixing this.
- You can now make a new file by right-clicking the directory tree. Thank you [rdbende](https://github.com/rdbende).
- Deleting an empty directory no longer asks you to confirm whether you surely want to delete it. Previously it would show a dialog that confusingly said "Do you want to permanently delete `foo` and everything inside it?", even if there was nothing inside the directory.

Running commands:
- If Porcupine is installed into a virtualenv, that no longer affects running commands. Previously Python would often fail to find libraries installed with `pip`.
- Output displayed in the Porcupine window now shows CRLF line endings (aka `\r\n`) correctly on all platforms. Previously it worked only on Windows, and on other systems, it showed a weird box at the end of the previous line.

Other improvements:
- Porcupine no longer prints weird things to the terminal when it is closed on Python 3.9. I haven't checked what other Python versions this affects.
- The X button that closes a tab is now white on dark themes, so it is easier to see. Thank you [rdbende](https://github.com/rdbende).
- The status bar now shows the number of words selected.
- URLs in code are now opened with Ctrl+Click or Ctrl+Enter (Command+Click or Command+Enter on MacOS). They previously used Alt+Shift instead of Ctrl, which was unnecessarily confusing. Thank you [1anakin20](https://github.com/1anakin20).
- Page up and down keys now work in the autocompletion list. Thank you [rdbende](https://github.com/rdbende).


## v0.99.1

Directory tree:
- Right-clicking a file or folder gives a menu with a few Git-related items in it. They now work. Previously they were sometimes disabled (grayed out) when they weren't supposed to be, and most of the time they didn't actually do anything when clicked. Thank you [rdbende](https://github.com/rdbende) for reporting this and helping me fix it.
- Empty folders are now refreshed correctly when they become non-empty. Previously empty folders would remain empty-looking even after creating files inside them, unless you closed and reopened the folder. Thank you [nicolafan](https://github.com/nicolafan).
- On MacOS, control+click now does the same thing as right-click. Thank you [1anakin20](https://github.com/1anakin20).

Running commands:
- "Repeat previous command" is now clever enough to not repeat commands from the wrong filetype. Previously it would happily run Python commands in C files.
- When the output is displayed in the Porcupine window, it now stays scrolled to the bottom as more output appears.
- File names and line numbers are now clickable in some cases that previously didn't work, such as `pytest` error messages.
- Pressing F5 in a HTML file will now open it in a web browser.

Other improvements:
- Entries in the find area (Ctrl+F) now stretch as you make the Porcupine window wider. This should make replacing long pieces of code easier. Thank you [rdbende](https://github.com/rdbende).
- The setting dialog is now tall enough to show all of its content by default, regardless of what Ttk theme you use. Thank you [rdbende](https://github.com/rdbende) for noticing and fixing this.
- Tooltips that appear when hovering code now have a similar background as the area itself, so if you use a dark theme, the tooltips will also have a dark background. Previously the colors would be opposite. Thank you [rdbende](https://github.com/rdbende).
- There is now automatic indenting when editing HTML files. Thank you [rdbende](https://github.com/rdbende).

Very small fixes:
- The plugin manager now shows a more meaningful description when the run plugin is selected.
- In a `switch` statement (e.g. C, C++, Java), you can press Alt+Enter instead of Enter to avoid automatic indentation when combining multiple `case foo:` statements. Alt+Enter is now mentioned in Porcupine's [default_filetypes.toml](https://github.com/Akuli/porcupine/blob/master/porcupine/default_filetypes.toml). Thank you [Tawishi](https://github.com/Tawishi).


## v0.99.0

I'm excited about this release. It has lots of awesome improvements, and several people have contributed to it. Thanks to all contributors!

New features:
- The run plugin has been rewritten. If you previously used it only for running Python code in a terminal by pressing F5, that will still work, although it can do a lot more. Press Shift+F5 to get started. My favorite feature is running commands so that their output goes to the Porcupine window, and things like `File "foo.py", line 52` become clickable links.
- Files in the directory tree can now be cut/pasted and copy/pasted by right-clicking them or with Ctrl+C and Ctrl+V. Thank you [nicolafan](https://github.com/nicolafan).
- The right-click menu of the directory tree now contains `git add` and a couple other Git operations.
- There is a new button "Jump to definition" in the *Edit* menu. For example, if you have a method call like `foo.bar()` in a Python program and you put the cursor on top of `bar`, this will take you to the line of code that looks like `def bar(self, ...`. The functionality itself isn't new, but it is now in the menubar, so it's easier to discover.

Bug fixes:
- Right-clicking and middle-clicking now works on MacOS. Thank you [1anakin20](https://github.com/1anakin20) for fixing this.
- The Windows installer now shows a very clear error message if you try to run it on a 32-bit Windows. Previously it would extract some files and then fail without a good error message. Thank you [Mannuel25](https://github.com/Mannuel25) for noticing this.
- When right-clicking a folder in the directory tree, one of the menu items is "Open in file manager". It now works on Windows.
- When uninstalling on Windows, Porcupine no longer deletes the whole directory chosen when installing it with the Windows installer. This means that the uninstaller will behave sanely even if you accidentally install Porcupine directly into `C:\Program Files` as opposed to e.g. `C:\Program Files\Porcupine`. You don't have to worry about this if you didn't choose a custom directory when installing Porcupine.
- Porcupine no longer kills `git status` if it runs for more than 2 seconds. This hopefully prevents errors where Git complains about a lock file (issue [#885](https://github.com/Akuli/porcupine/issues/885)). Porcupine runs `git status` internally to figure out how to color files in the directory tree, e.g. green for `git add`ed.

Other improvements:
- Porcupine now uses a dark theme by default, although you won't notice it if you have chosen a custom theme. To change the theme, there is a new button in the *Porcupine Settings* dialog (in *Edit* menu), and the old *Syntax Colors* menu has been removed.
- Many small UI details have been improved. For example, many buttons are now wider than before, so it's easier to click them. Thank you [rdbende](https://github.com/rdbende).
- You can now uncheck Python virtualenvs after right-clicking them in the directory tree. This means that you can choose to not use a virtualenv even if the project has one. This is useful if something isn't working, and you suspect there might be something wrong with the virtualenv.
- On Windows, Python virtualenvs now show up as selected immediately after selecting them in the directory tree.
- Files whose name starts with a dot are now grouped after other files in the directory tree. Previously they were first, which is annoying, as these files are by convention hidden and usually you want to ignore them. Thank you [nicolafan](https://github.com/nicolafan) for fixing this.
- Porcupine no longer comes with `pycodestyle`, so you should get less yellow underlines when editing Python files. Nowadays many Python projects use `black`, so enforcing `pycodestyle`'s coding style doesn't make sense.
- You now get a warning if you try to open a huge file. Previously Porcupine would open it without checking the size, and in the worst possible case, freeze the whole computer. Thank you [rdbende](https://github.com/rdbende) for fixing this.
- A few smaller improvements and fixes that I don't expect most users to notice.


## v0.98.2

The relevant part of CHANGELOG.md is now shown on the releases page. I manually added it to the releases page for v0.98.0. You can read all changelogs [here](https://github.com/Akuli/porcupine/blob/master/CHANGELOG.md).


## v0.98.1

A failed attempt to fix showing CHANGELOG.md contents on the releases page.


## v0.98.0

New features:
- From now on, the relevant parts of this changelog should appear on the releases page on GitHub.
- Several new features in the directory tree:
    - The directory tree now acts as more of a file manager than before. You can right-click files and folders to e.g. rename or delete them.
    - You can now type a character to navigate. For example, pressing the `a` key cycles through all files in the selected directory whose name starts with `a`.
    - Right-clicking a project now offers you an option to hide it from the directory tree. It will appear again when you open a file inside the project.

Bug fixes:
- Syntax highlighting now works in code blocks of Markdown files. Previously they would sometimes display weirdly depending on scrolling. Thank you [rdbende](https://github.com/rdbende) for reporting this.
- Porcupine no longer segfaults on systems with the Noto Color Emoji font installed, regardless of what version of Tcl/Tk it uses. Thank you Tuomas for fixing this.
- Some menu items, such as most items in the *Edit* menu, are now grayed out when there are no open tabs or the currently selected tab is not a regular tab for editing text files. Previously they would appear clickable, but clicking them would do nothing visible and cause an error to be logged.
- Remembering the opened tabs when restarting now works regardless of what is configured in `filetypes.toml`.

Other changes:
- The Windows installer is slightly smaller than before, 19.2MB instead of 22.7MB.
- The tetris plugin was deleted. It was never included by default, and it will likely continue to work for a few releases if you installed it manually from `more_plugins/`. Use [Arrinao's tetris project](https://github.com/Arrinao/tetris) if you want to play tetris.
- Porcupine now uses a different library for parsing `filetypes.toml` and `default_filetypes.toml`. If you have customized your `filetypes.toml` and you get errors when starting Porcupine, you may need to switch to slightly different syntax. See `default_filetypes.toml` for examples of what works (there is a link to it in your user-specific `filetypes.toml`).

There are also other small improvements.


## v0.97.0

New features:
- Alt+Shift+C+E sets anchors to every yellow or red underline.
    This is useful for stepping through all errors in a file and fixing them one by one.
    See *Anchors* in the *Edit* menu.
- You can now run `isort` from the *Tools/Python* menu.
- The status bar has new buttons for choosing the line ending and encoding.
    Also, if you select a single character, it displays information about that character.
    This can be useful if you want to distinguish `“` and `"`, for example.

Bug fixes:
- When Porcupine detects a file that has a Git merge conflict,
    it creates "Use this" and "Edit manually" buttons to help resolve it.
    They no longer show up weirdly on top of tooltips and autocompletion popups.
- The *Wrap long lines* setting (in View menu) is now preserved
    when restarting Porcupine or dragging a tab out of Porcupine.
- Line numbers now update when unfolding, even in very short files.
    Speaking of folding, the fold plugin is currently not very easy to use,
    and I am planning to improve it ([#410](https://github.com/Akuli/porcupine/issues/410)).

There are also other small improvements.


## v0.96.0

- The minimap (the thing that shows your code on the side with small font)
    is no longer ridiculously wide.
    You can also resize it by dragging with the mouse.
    If you previously disabled it because it was too wide,
    you can re-enable it in the plugin manager.
- The long line marker can no longer move to the wrong place in unpredictable ways.
- Changing the filetype now deletes yellow and red underlines from the file being edited.
    If you somehow open a C file as if it was a Python file,
    it is probably full of complaints about invalid Python syntax,
    and you want them to go away when you choose C from the Filetypes menu.
- Better error handling for opening and saving files:
    - If you open a file written with the wrong encoding,
        let's say a file using Latin-1 but Porcupine thinks it's UTF-8 (default),
        Porcupine will now ask you which encoding the file uses,
        and mentions using [.editorconfig files](https://editorconfig.org/) to change it permanently.
        There is also error handling for encoding errors when saving files.
    - Porcupine now shows an error message if a file is deleted while it is open in Porcupine.
        Previously it would prevent you from opening more files, with no visible error messages,
        until the tab with the non-existing file was closed.
        This was a bug, not a feature.
    - Many other improvements that you are unlikely to come across when using Porcupine normally.
- Several smaller improvements.


## v0.95.0

Windows improvements:
- Automatic indentation now works on Windows.
    For example, if you type `def foo():` into a Python file and press Enter,
    the next line will be indented.
    Press Alt+Enter instead of Enter to prevent getting the additional indent.
- You can now right-click a Python file and choose to open it in Porcupine.
    This works not only for Python files, but for all file types that are defined in
    [default_filetypes.toml](https://github.com/Akuli/porcupine/blob/v0.95.0/porcupine/default_filetypes.toml).
    You can open other files in Porcupine by right-clicking them too,
    but it takes a few more clicks.
- Porcupine now shows up as `Porcupine.exe` in the task manager.
    It previously showed up as `pythonw.exe`.
    Let me know if your antivirus program dislikes `Porcupine.exe`
    (it is not malware, but sometimes Windows Defender
    complains about executables it hasn't seen before).
- Porcupine installer now displays an error message if Microsoft Visual C++ Redistributable is not installed.
    Porcupine has never worked without it, but previously it would install silently.
    If you see the error message, search it with Google.

Other fixes:
- Porcupine can no longer start off-screen if your screen size changes.


## v0.94.3 and older

No change log, but you can browse the Git commit history.
Let me know if you need help with that.
