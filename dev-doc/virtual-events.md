# Virtual Events

If you are tempted to make a list of callback functions, expose it to another part of Porcupine,
and then call each function in the list, you should probably use a virtual event instead.
Here's how they work:

```python
def print_hi(event):
    print("hi")

some_widget.bind("<<PrintHi>>", print_hi, add=True)
some_widget.event_generate("<<PrintHi>>")  # this prints hi
```

You can name virtual events anything you want as long as you use the double `<<` and `>>`.
There are some predefined virtual events, but you likely won't clash with them by accident.

Virtual events are specific to a widget.
Nothing will happen if you `.bind()` and `.event_generate()` on different widgets.
This is useful for things that only affect one tab, for example.

Make sure to spell virtual events the same way in all places.
**You will get no errors if you misspell the name of a virtual event.**
Your callbacks just won't run.


## Multiple Callbacks

(Actually, this section applies to all tkinter events, not just virtual events.)

With `add=True`, you can bind multiple things to the same virtual event.
This is almost always what you should do in Porcupine.
For whatever reason, the default is `add=False`, which deletes all existing bindings.

```python
def print_hi(event):
    print("hi")

def print_hello(event):
    print("hello")

some_widget.bind("<<PrintHi>>", print_hi, add=True)
some_widget.bind("<<PrintHi>>", print_hello, add=True)
some_widget.event_generate("<<PrintHi>>")  # prints hi and hello
```

You can return the string `"break"` from a callback function to prevent running other
callbacks that have been added afterwards.

```python
def print_hi(event):
    print("hi")
    return "break"    # <--- This stops processing the event

def print_hello(event):
    print("hello")

some_widget.bind("<<PrintHi>>", print_hi, add=True)
some_widget.bind("<<PrintHi>>", print_hello, add=True)
some_widget.event_generate("<<PrintHi>>")  # only prints hi
```

This is typically used together with [setup_before and setup_after](architecture-and-design.md#loading-order)
to decide which plugin gets to handle a virtual event.


## Passing Data

It is possible to pass data when generating a virtual event
and receive (a copy of) the data when the `.bind()` callback runs.
See the docstring of the `porcupine.utils.bind_with_data()` function for details.
You need to use a function from `porcupine.utils` because
Tkinter doesn't expose this functionality very nicely,
but it is needed often because Porcupine relies quite heavily on virtual events.


## Simple Example: `<<Reloaded>>`

**Source Code:**
- [porcupine/tabs.py](../porcupine/tabs.py) (search for `<<Reloaded>>`)
- [porcupine/plugins/mergeconflict.py](../porcupine/plugins/mergeconflict.py)

A couple things need to happen when a file's content is read from disk and placed into a text widget.
For example, if the file contains [Git merge conflicts](https://akuli.github.io/git-guide/branches.html#merges-and-merge-conflicts),
the `mergeconflict` plugin will notice them and show a nice UI for resolving them.

To implement this, we need some way to run code in a plugin when the core is done reloading a file's content.
We obviously cannot import from `porcupine.plugins.mergeconflict` in the core,
so we need some sort of callbacks,
and because this is Porcupine, we use virtual events for the callbacks.

Specifically, the `mergeconflict` plugin binds to `<<Reloaded>>` on each new tab.
Here's how it works:
1. Porcupine's core reads a file's content from disk and places into a text widget.
2. Porcupine's core generates a `<<Reloaded>>` event.
3. The `mergeconflict` plugin has done a `.bind("<<Reloaded>>", ...)`,
    so a function in the `mergeconflict` plugin runs.
4. The `mergeconflict` plugin finds all merge conflicts in the file and does its thing.


## Complex Example: jump to definition

**Source Code:**
- [porcupine/plugins/jump_to_definition.py](../porcupine/plugins/jump_to_definition.py)
- [porcupine/plugins/langserver.py](../porcupine/plugins/langserver.py) (search for `jump_to_def`)
- [porcupine/plugins/urls.py](../porcupine/plugins/urls.py)

Let's say you have a line of Python code that looks like `self.do_something()`.
If you bring the cursor to the middle of `do_something()` and press Ctrl+Enter,
or if you control-click `do_something`,
Porcupine will take you to a line of code that looks something like `def do_something(self):`.

This is implemented in two different plugins:
- The `langserver` plugin is responsible for finding the `def do_something(self):` line from your project.
- The `jump_to_definition` plugin does everything else.

The `jump_to_definition` plugin doesn't know anything about the langserver plugin.
All it knows is that the user requests a jump-to-definition,
and eventually it gets a response telling it where to go.
This is great, because langserver isn't necessarily the only way to find out where something is defined.
For example, if you have `https://example.com/` in your code and you Ctrl+Enter on it,
that is *also* a jump-to-definition as far as Porcupine is concerned,
although the "definition" is a website in this case and it opens in a browser window.

More specifically, here's what happens when you press Ctrl+Enter on `self.do_something()`:

1. The `jump_to_definition` sees the Ctrl+Enter. It generates a `<<JumpToDefinitionRequest>>` virtual event.
2. The `urls` plugin has done a `.bind("<<JumpToDefinitionRequest>>", ...)`, but it ignores the event.
2. The `langserver` plugin has done a `.bind("<<JumpToDefinitionRequest>>", ...)`,
    so a function in the `langserver` plugin runs.
3. The `langserver` plugin figures out where the `def do_something(self):` line is.
    This will take a while. Porcupine doesn't freeze when this happens.
4. The `langserver` plugin generates a `<<JumpToDefinitionResponse>>` virtual event.
5. The `jump_to_definition` plugin has done a `.bind("<<JumpToDefinitionResponse>>")`,
    so it receives the response from the `langserver` plugin.
6. The `jump_to_definition` plugin takes you to the `def do_something(self):` line.

And here's what happens when you press Ctrl+Enter on a URL:

1. The `jump_to_definition` sees the Ctrl+Enter. It generates a `<<JumpToDefinitionRequest>>` virtual event.
2. The `urls` plugin has done a `.bind("<<JumpToDefinitionRequest>>", ...)`,
    so a function in the `urls` plugin runs.
3. The `urls` plugin opens the URL in the default web browser.
4. The `urls` plugin returns `"break"` to prevent the `langserver` plugin from handling the event.
