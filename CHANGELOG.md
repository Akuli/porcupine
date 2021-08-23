Unlike the Git commit history, this changelog does not include code cleanups
and other details that don't affect using Porcupine.


## UNRELEASED

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


## 0.95.0

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


## 0.94.3 and older

No change log, but you can browse the Git commit history.
Let me know if you need help with that.
