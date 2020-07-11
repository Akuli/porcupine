# Tkinter stubs done right

This directory contains my own mypy stubs for tkinter. These stub files tell
what arguments of what types each tkinter method takes.


## Running mypy with my stubs

Make sure that you have Python 3.8 or later.

```
$ MYPYPATH=my_stubs mypy porcupine/
```


## IDE support

If your IDE or editor uses mypy for checking types, then you need to run your
IDE with `MYPYPATH` set as above. For example, let's say that typing
`idecommand` on a terminal starts your IDE. Then you need to run this instead:

```
$ MYPYPATH=/absolute/path/to/porcupine/my_stubs idecommand
```

You can also try this with a relative path instead of an absolute path. That
may or may not work depending on how your IDE runs mypy.

If you want a challenge, you can also try telling your IDE to set the
environment variable when running mypy instead of setting it for the whole IDE.


## How these stubs differ from the default stubs

By default, mypy uses stub files from [typeshed](https://github.com/python/typeshed/tree/master/stdlib/3/tkinter).
The tkinter stubs in typeshed have several issues:
- Many methods are untyped, such as this one:

    ```python3
    def after_idle(self, func, *args): ...
    ```

    If you use mypy's `--strict` flag, then you can't use `after_idle` or any
    other untyped method at all with the typeshed tkinter stubs. Without
    `--strict`, you can use `after_idle`, but you won't get any mypy errors if
    you specify the callback function incorrectly.

- `typing.Any` is used way too much.
- Some modules like `tkinter.font` and `tkinter.simpledialog` are missing.
- The stubs don't support `'??'` in `tkinter.Event` fields. Many
  `tkinter.Event` fields get set to the string `'??'` when the field is not
  available for whatever reason. Do this with my stubs:

    ```
    def event_handler(event: tkinter.Event) -> None:
        
    ```

There are also some issues with my tkinter stubs:
- My stubs don't supports constants such as `tkinter.END` for the string
  `'end'`. Don't use those constants. They are dumb.
- Many widget options are missing because every properly supported widget
  option means somewhat time-consuming work and a lot of copy/pasta. The
  copy/pasta comes from how all options can be used in 3 different ways:
    - `__init__` option for `tkinter.ttk.Label(text="bla")`
    - `__setitem__` overload for `label['text'] = "bla"`
    - `__getitem__` overload for `print(label['text'])`

    The somewhat time-consuming work involves looking at Tk's manual pages and
    trying to guess a reasonable type for the option based on my experience
    with using that option in Porcupine and other projects.

    For most options, `__getitem__` is not supported at all because I don't use
    it much and it's a lot of work to add. The `__getitem__` type of an option
    may differ from other types. For example, if you do `button['command']`
    after `button = ttk.Button(command=print)`, you won't get the Python
    `print` function; you will get Tcl code that runs the Python `print`
    function. To catch these, I run all `__getitem__` calls on Python's `>>>`
    prompt before adding them to a stub file.
- Many methods are missing, including many methods that are in the typeshed
  stubs. In particular, `config` and `configure` are missing to avoid another
  entry in the above copy/pasta list. Treat the widgets as dicts instead as
  shown above.
- Most `tkinter` widgets are missing, such as `tkinter.Button`. Please use
  `ttk` widgets such as `ttk.Button` instead. I'm not interested in supporting
  most of the "old-style" non-Ttk widgets because they just don't look good on
  most operating systems and I can't use
  [ttkthemes](https://github.com/TkinterEP/ttkthemes) with them.
- Sometimes there are multiple ways to call methods and my stubs support only
  one of them. For example, `after` is typically called like this:

    ```python3
    def after(self, ms: int, func: Callable[[], None]) -> str: ...
    ```

    But it can be also used like this, or with any other argument types instead
    of `int, float, bool`:

    ```python3
    def after(self, ms: int, func: Callable[[int, float, bool], None],
              arg1: int, arg2: float, arg3: bool) -> str: ...
    ```

    Or like this to sleep for `ms` milliseconds similarly to `time.sleep`:

    ```python3
    def after(self, ms: int) -> None: ...
    ```

    My stubs only support the first way to call `after` because I never use the
    other ways.


## Why not pull request?

Putting my tkinter stubs to typeshed would break backwards compatibility in
many ways and cause more maintaining work:
- Any code using constants like `tkinter.END` would need to be changed to use
  strings like `'end'` instead or I would need to add support for `tkinter.END`
  and similar constants.
- If a method is missing from my stubs but present in what's currently in
  typeshed, then all mypy-checked code using that method will stop working.
- If someone calls a tkinter method in a way that I have never used, such as
  `after(ms)` in the above example, then they would start getting mypy errors.
- My stubs use `typing.Literal` generously. That's new in Python 3.8, but
  typeshed stubs need to be backwards compatible.
- My stubs don't support `__setitem__` and `__getitem__` with arbitrary
  strings. This is done to prevent typos, but this also means that missing
  support for an option creates a mypy error, and again, breaks backwards
  compatibility. I don't want to add support for every possible option of every
  widget, because that's a lot of work but not very rewarding. Presumably other
  people would feel the same way if I asked someone to help with this.
- Support for new options need to be added every time a new version of Tk is released.
- In the past, typeshed contributors
  [decided](https://github.com/python/typeshed/pull/4200) to not support `'??'`
  in `tkinter.Event` (see above). My `tkinter.Event` does that "right" and
  supports `'??'`, and a lot of  `assert thing != '??'` would need to be added
  to mypy checked code to make it work with my stubs.
- My stubs require that `bind` callbacks return `None` or `'break'`. They can
  actually return pretty much anything, and anything else than `'break'` will
  be treated the same. The generous use of `Any` in typeshed tkinter stubs
  means that code returning something else than `'break'` works with typeshed
  stubs but not with my stubs
