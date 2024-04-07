# Settings

This file describes how [porcupine/settings.py](../porcupine/settings.py) works
and what things were considered when designing it.

First, to prevent confusion, let's define some terms:

| Term          | Description                                                       |
|---------------|-------------------------------------------------------------------|
| option        | a key-value pair in the settings, e.g. "the font size is 12"      |
| option name   | identifier string that refers to an option, e.g. `"font_size"`    |
| value         | the value of an option is what users can change, e.g. `12`        |


## Key Features / Design Requirements

Here are the requirements I had in mind when designing the `porcupine.settings` module:
- Two kinds of settings: global and tab-specific
- Load and save a somewhat human-readable JSON file (`settings.json` contains the global settings)
- Load from human-editable TOML file (`filetypes.toml` contains tab-specific settings)
- Type of a value can be e.g. `str`, `int`, `bool`, `pathlib.Path`, any enum, a simple custom class
- Setting changed callbacks using [virtual events](virtual-events.md)
- Behaves nicely with static type checking
- Plugins can define new options
- No error if JSON file contains unknown options (explained in detail below)
- Settings can be set with different priorities, and the value set with the highest priority will be used.
    For example, [editorconfig](https://editorconfig.org/) should have higher priority
    than Porcupine's defaults for a given filetype.


## Types

Unfortunately, "Behaves nicely with static type checking" contradicts with
"Plugins can define new options".
For the nicest possible type checking, the type checker would need to know
what settings exist and what their types are.
To teach that to the type checker,
we would need to list all settings and their types in `porcupine/settings.py`, like this:

```python
class GlobalSettings:
    font_family: str
    font_size: int
    ask_to_pastebin: bool
    ...
```

Now `porcupine/settings.py` knows about the `ask_to_pastebin` setting that belongs to
[the pastebin plugin](../porcupine/plugins/pastebin.py).
This is unacceptable to me.
Even though [plugins sometimes depend on each other](architecture-and-design.md#communicating-between-plugins),
I don't want the core of Porcupine to know anything about specific plugins.

The solution is to settle for slightly worse type checking:
- The type of a setting is given when the setting is defined.
    This can be in the core of Porcupine or in a plugin, depending on the setting.
    For example, here's how plugins define new global settings:
    ```python
    from porcupine.settings import global_settings

    ...

    def setup() -> None:
        ...
        global_settings.add_option("foo", type=int, default=5)
        ...
    ```
- When getting the value of a setting, you need to provide the type,
    so that the type checker knows what you get:
    ```python
    value = global_settings.get("foo", int)
    ```
    If the type isn't the same as when defining the option,
    then `.set()` will fail regardless of the current value of the setting.
- When setting the value of a setting, you don't specify a type.
    We could make types required here similarly to getting, but
    checking the type at runtime seems to be good enough in practice.
    ```python
    global_settings.set("foo", 20)
    ```

For types that allow `None`, such as `int | None`,
we also need an ugly workaround for a mypy bug.
See the docstring of the `get()` method
(search for `def get` in [porcupine/settings.py](../porcupine/settings.py)).


## Change Events

After the value of a global setting `foo` changes,
**every tkinter widget in Porcupine** receives a virtual event `<<GlobalSettingChanged:foo>>`.
After the value of a tab-specific setting `foo` changes,
**only the tab** receives a virtual event `<<TabSettingChanged:foo>>`.

The reason for "broadcasting" change events of global settings to all widgets
is to let you decide the duration (lifetime) of the bind.
For example, [the longlinemarker plugin](../porcupine/plugins/longlinemarker.py) does this:

```python
self.tab.bind("<<TabSettingChanged:max_line_length>>", self.do_update, add=True)
self.tab.bind("<<GlobalSettingChanged:font_family>>", self.do_update, add=True)
self.tab.bind("<<GlobalSettingChanged:font_size>>", self.do_update, add=True)
```

Because the global change events are bound using a tab's `.bind()`,
`self.do_update()` will no longer be called after the tab has been closed.
This is good, because trying to do something with a closed tab
would probably cause a lot of tkinter errors.
In general, bindings stay alive only as long as the widget whose `.bind()` method was used.
With `<<TabSettingChanged:...>>` events, you don't have much of a choice, as they are only available on tabs.


## Unknown Options

Global settings are saved to a JSON file.
For example, on this linux system,
it is `/home/akuli/.config/porcupine/settings.json` and it looks like this:

```json
{
    "directory_tree_projects": [
        "/home/akuli/difcuit",
        "/home/akuli/typeshed",
        "/home/akuli/porcupine",
        "/tmp",
        "/home/akuli/kuitit"
    ],
    "directory_tree_width": 214,
    "default_geometry": "1678x963+0+0",
    "ask_to_pastebin": false,
    "run_command_output_height": 243,
    "python_venvs": {
        "/home/akuli/musamatikka": "/home/akuli/musamatikka/env",
        "/home/akuli": null,
        "/home/akuli/autolayout": "/home/akuli/autolayout/env",
        "/tmp": null,
        "/home/akuli/mittari": "/home/akuli/mittari/env",
        "/home/akuli/bot": "/home/akuli/bot/env",
        "/home/akuli/bottelo": "/home/akuli/bottelo/env",
        "/home/akuli/mantaray": "/home/akuli/mantaray/env",
        "/home/akuli/potti": "/home/akuli/potti/env",
        "/home/akuli/typeshed": null,
        "/home/akuli/porcupine": "/home/akuli/porcupine/env",
        "/home/akuli/difcuit": "/home/akuli/difcuit/env"
    },
    "minimap_width": 31
}
```

This file contains only the settings that differ from their default values.
For example, there's no `"font_family"` or `"font_size"`,
because I'm happy with the font that Porcupine uses by default.
This way, if the default value is changed,
then users who never touched the setting will get the new default.

When the JSON file is loaded, Porcupine doesn't know anything about many settings in it.
At that point, they are called **unknown options**.
Here are some ways to end up with unknown options:
- Disabling plugins: If I disable [the minimap plugin](../porcupine/plugins/minimap.py),
    then Porcupine won't know what `"minimap_width": 31` means,
    and that is an unknown option.
- Downgrading Porcupine: Sometimes newer versions of Porcupine have options that older Porcupine versions don't,
    but they share the same JSON file.
    If a user goes back to an older version of Porcupine for whatever reason,
    then that older version will see a bunch of unknown options.
- Loading settings before plugins: The JSON file is loaded before the plugins,
    because plugins need to access the settings.
    This means that if a plugin's `setup()` adds a new option,
    there will be an unknown option in the settings before `setup()` runs.

In short, unknown options are unavoidable, and it's important to handle them properly.
Porcupine never destroys unknown options.
Instead, it remembers them and writes them back to the JSON file.

This isn't the only reason to remember unknown options.
When a plugin loads, it may define some settings and then immediately `.get()` their values.
To make this possible, the JSON file is loaded before the plugins.
Options defined in plugins are is initially
