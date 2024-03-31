# Structure of Plugins

This file documents things that have special meanings in Porcupine plugins.


## Module Docstring

The docstring of the plugin (aka "that multiline comment-like thingy at start of the file")
is the description that shows up in Porcupine's plugin manager.
To open the plugin manager, select *Plugin Manager* in the *Settings* menu.

The docstring should make sense for users who are not familiar with Porcupine internals
and who just want to disable unwanted features in the plugin manager.
Ideally, any user would understand what the plugin does by just reading the description.


## `setup()`, `setup_before`, `setup_after`

See [architecture-and-design.md](architecture-and-design.md).


## `setup_argument_parser(parser: argparse.ArgumentParser)`

This function is optional, and most plugins don't need this.

When Porcupine starts, it calls `setup_argument_parser()` functions
much earlier than `setup()` functions,
before command-line arguments are parsed.
The intended use case is adding command-line arguments.
To help with that, Porcupine passes its instance of
[`argparse.ArgumentParser`](https://docs.python.org/3/library/argparse.html) as an argument.


## `on_new_filetab(tab: tabs.FileTab)`

This function name is **not special** to Porcupine,
but it's documented here because many plugins have this function,
together with this line in `setup()`:

```python3
get_tab_manager().add_filetab_callback(on_new_filetab)
```

This causes Porcupine to call the `on_new_filetab()` function for every `FileTab`.
If the plugin is enabled while Porcupine is running, it will be called on all existing `FileTab`s as well.
