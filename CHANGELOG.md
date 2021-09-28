Unlike the Git commit history, this changelog does not include code cleanups
and other details that don't affect using Porcupine.


## v0.98.0

New features (all in the directory tree):
- The directory tree now acts as more of a file manager than before.
    You can right-click files and folders to e.g. rename or delete them.
- You can now type a character to navigate.
    For example, pressing the `a` key cycles through all files in the selected directory
    whose name starts with `a`.
- Right-clicking a project now offers you an option to hide it from the directory tree.
    It will appear again when you open a file inside the project.

Bug fixes:
- Syntax highlighting now works in code blocks of Markdown files.
    Previously they would sometimes display weirdly depending on scrolling.
    Thank you [rdbende](https://github.com/rdbende) for reporting this.
- Porcupine no longer segfaults on systems with the Noto Color Emoji font installed,
    regardless of what version of Tcl/Tk it uses.
    Thank you Tuomas for fixing this.
- Some menu items, such as most items in the *Edit* menu,
    are now grayed out when there are no open tabs
    or the currently selected tab is not a regular tab for editing text files.
    Previously they would appear clickable,
    but clicking them would do nothing visible and cause an error to be logged.
- Remembering the opened tabs when restarting now works
    regardless of what is configured in `filetypes.toml`.

Other changes:
- From now on, the relevant parts of this changelog should appear on the releases page on GitHub.
- The Windows installer is slightly smaller than before, 19.2MB instead of 22.7MB.
- The tetris plugin was deleted.
    It was never included by default,
    and it will likely continue to work for a few releases
    if you installed it manually from `more_plugins/`.
    Use [Arrinao's tetris project](https://github.com/Arrinao/tetris)
    if you want to play tetris.
- Porcupine now uses a different library for parsing `filetypes.toml` and `default_filetypes.toml`.
    If you have customized your `filetypes.toml` and you get errors when starting Porcupine,
    you may need to switch to slightly different syntax.
    See `default_filetypes.toml` for examples of what works
    (there is a link to it in your user-specific `filetypes.toml`).

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
