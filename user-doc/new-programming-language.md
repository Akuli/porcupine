# Getting Porcupine to work with a programming language

People often ask whether Porcupine supports a programming language X.
This page lists all the things that you may want to do for using Porcupine with a programming language.

Feel free to [create an issue on GitHub](https://github.com/Akuli/porcupine/issues/new)
if you get any issues with following this guide.
It might also be a good idea to create an issue if you follow this guide successfully,
so that your working settings can be added to Porcupine's default settings.


## How to edit filetypes.toml

`filetypes.toml` is Porcupine's configuration file for programming language specific settings.
You can find it in the *Config Files* section of the *Settings* menu at top.
You need to save your `filetypes.toml` and restart Porcupine to see the changes being applied.

Your `filetypes.toml` should contain a URL pointing to Porcupine's default `default_filetypes.toml`.
I recommend reading `default_filetypes.toml` because
it contains lots of example configurations and
every possible option is documented there.

If the programming language X is already listed in `default_filetypes.toml`,
you can still override its settings in your own `filetypes.toml`.
For example, if you want C code to be indented with tabs by default,
you can add this to your `filetypes.toml`:

```toml
[C]
tabs2spaces = false
```

That said, you should use [`.editorconfig` files](https://editorconfig.org/) for project-specific settings.
Porcupine uses `.editorconfig` settings whenever they disagree with `filetypes.toml`.
For example, if you open source code of the Python interpreter (written in C),
Porcupine will use spaces for indentation regardless of your `filetypes.toml` settings,
because Python's source code comes with
[this `.editorconfig` file](https://github.com/python/cpython/blob/main/.editorconfig)
that sets `indent_style = space`.

If the programming language X is not in `default_filetypes.toml`,
then copy the configuration of some other programming language Y from `default_filetypes.toml`
and modify it.
You need at least `filename_patterns` for detecting when to use the settings
and `pygments_lexer` for syntax highlighting.

If you want to reset all changes you have done to your `filetypes.toml`, just delete it
and restart Porcupine. It will create a new `filetypes.toml`.


## Autocompletions with langserver

Porcupine's autocompletions work with a langserver.
It's a program that runs on your computer and doesn't use the internet at all,
unlike you might guess from the name.
Porcupine requests completions from the langserver and displays them to you.

Start by finding and installing a langserver for the programming language X.
I don't have any more detailed instructions, because this depends a lot on which programming language is in question.
Search the internet.

When the langserver is installed, you should be able to invoke it from the terminal or command prompt with some command.
For example, running `pyls` on the terminal starts the
[Python language server](https://github.com/palantir/python-language-server)
that Porcupine uses by default with Python.
Running `pyls --verbose` does the same, but also prints some information about what's happening.
Here's the configuration required for that:

```toml
[Python.langserver]
command = "pyls"
language_id = "python"
```

Set `command` to whatever command you want, specifying absolute paths as necessary.
The comment in `default_filetypes.toml` explains how to find the correct value for `language_id`.

For Python and `pyls`, the actual configuration in `filetypes.toml` is more complicated, but you don't need to care about that.

Most langservers use stdin and stdout to communicate with the editor.
Some langservers instead use a TCP socket listening on localhost.
For example, `pyls --tcp` uses a TCP socket but just `pyls` uses stdin and stdout.
**Porcupine does not support connecting to a langserver with TCP**,
because it would be more work to configure and leads to a subtle bug.
In fact, Porcupine used to support connecting with TCP, but nobody used that feature.
If you need to use a langserver that only supports TCP for some reason, please create an issue.


## Debugging

The error reporting for invalid `filetypes.toml` is pretty bad.
If you have any trouble with this, please create an issue on GitHub,
and ask us to make it more user-friendly.

If your `filetypes.toml` contains something invalid, then Porcupine will print a
warning message to the terminal or command prompt (if any) and start normally.
But if you start Porcupine without a terminal or command prompt,
you will never see these messages.
In that case, you need to look at Porcupine's log files.
To find the log files, open *Porcupine debug prompt* from the *Run* menu
and type `print(dirs.user_log_path)`.

To get more output on the terminal or command prompt,
add `--verbose-logger=porcupine.plugins.langserver` to the end of the command that starts Porcupine.
This doesn't affect the log file, it only tells Porcupine to print more things to the terminal.

If no section in `filetypes.toml` or `default_filetypes.toml` has `filename_patterns`
specified so that it matches a file,
then Porcupine may still be able to get syntax highlighting to work.
However, Porcupine won't syntax highlight anything
if there is a section with a matching `filename_patterns` that doesn't define how to do syntax highlighting.
