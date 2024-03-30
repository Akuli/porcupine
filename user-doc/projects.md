# Working with Python projects

For one-file scripts, you can just [make a new file and run it](getting-started.md).
This project explains the recommended way to work with larger projects.


## Project Root and Directory Tree

After downloading a project you want to work on (with e.g. `git clone`),
just open any file from the project in Porcupine.
The directory tree at left will look something like this:

![Directory tree](images/directory-tree-nothing-opened.png)

Here `~/porcupine`, `~/difcuit`, `~/automata`, `~` and `/tmp` are **project root folders**.
This is the folder where all files of a project will go.
For projects that use Git, this folder is usually created by running `git clone` on terminal.
The `~` character means your home folder.
It is typically `C:\Users\YourName` on Windows, `/Users/YourName` on MacOS and `/home/yourname` on Linux.
For example, on my computer, `~/porcupine` actually means `/home/akuli/porcupine`.

Double-click the project root folder in the directory tree to have a look inside.
You will see the files in the project.
After working on a project for a while, the directory tree will look something like this:

![Directory tree, with more stuff](images/directory-tree-stuff-opened.png)

Colors appear only in projects that use Git.
The meanings of the colors are similar to `git status`:
- Green = contains changes have been `git add`ed, so that the changes will be included in the next Git commit
- Bright red = contains changes that won't be included in the next Git commit, unless you `git add` them
- Dark red = Git knows nothing about this file or folder, and it won't be included in the next commit
- Gray = this file or folder has been ignored using `.gitignore` and isn't meant to be committed


## Project Root Detection

Currently the logic for finding the project root is:
1. If the file is inside a Git repository (e.g. created by `git clone`),
    then the Git repository becomes the project root.
    For example, I am currently editing `/home/akuli/porcupine/user-doc/projects.md`,
    and Porcupine has detected `/home/akuli/porcupine` as the project root
    because it is a Git repository.
2. If Git isn't used but there is a README or [`.editorconfig` file](https://editorconfig.org/),
    then the project root is the folder where the README or `.editorconfig` is.
    (Porcupine supports editorconfig files.)
    For README files, Porcupine recognizes any file extension and any reasonable capitalization,
    so README.md, ReadMe.TXT and readme.rst are all valid.
    So even if your project doesn't use Git, Porcupine is still likely to recognize it correctly.
3. If all else fails, the directory containing the file is used.
    This is why `~` and `/tmp` show up as projects for me.
    I have edited a couple scripts that have been directly in those folders.

If all else fails, the directory containing the file is used as the project root.


## Virtual environments, aka venvs

This section only applies to Python projects.

Any large Python project has many dependencies.
You could just `pip install` them all into your system, but:
- When you no longer want to work on a project, there's no good way to uninstall the dependencies of that project.
- If `pip` doesn't work for whatever reason, you will probably have the same problem in all projects.
- Different projects might need different, incompatible versions of the same dependency.

Venvs fix these problems.
A venv is a folder that contains all your dependencies,
and prevents you from polluting your system's Python with libraries.
If you no longer want to work on a project, just delete the venv folder.

I recommend making one venv for each project that has dependencies.

To create a venv, start by opening a terminal in the project root folder.
For example, you can right-click the project root in Porcupine and select *Open in terminal*.

![Open in terminal](images/open-in-terminal.png)

Let's create a venv named `env`, activate it, and install a library into it:

```
$ python3 -m venv env
$ source env/bin/activate
(env)$ pip install requests
```

This should look something like this:

![Installing dependencies into venv](images/venv-pip-install.png)

If you are on Windows,
use `py` instead of `python3`, and use `env\scripts\activate` instead of `source env/bin/activate`.

Activating the venv means that `pip`, `python` and other commands point to things inside the venv.
So if you say `pip install requests` with a venv activated, you are running the venv's pip,
and it will install into the venv, not globally.

Now go back to Porcupine. You should see a new folder named `env` with a ![yellow venv marker](../porcupine/images/venv.png) next to it.
This means that Porcupine found your venv and will use it.
If Porcupine doesn't find your venv, or you have multiple venvs and Porcupine uses the wrong one,
you can choose the venv to use by right-clicking it:

![Right-click menu for selecting venv](images/venv-right-click.png)

Let's [create and run a file](getting-started.md) that uses `requests`.
You will see that Porcupine activates the venv before it invokes Python to run the file,
so `import requests` succeeds:

![Running a program that uses requests](images/venv-run.png)

The `.` at the start of the activating command means the same thing as `source`.


## Running the project

By default, Porcupine runs `python3 {file_name}` when you press F5.
This works well for small scripts, but not for most larger projects.

Press Shift+F5 to decide how Porcupine will run the project.
These settings work for many Python projects:
- Run this command: `python3 -m {project_name}`
- In this directory: `{project_path}`

Let's say the project name is `foo`.
Then the resulting command will be `python3 -m foo` in the project root folder.
It basically tells Python to run `foo.__main__` so that `import foo` works.
In other words, it assumes a file structure that looks something like this:

```
foo/
    README.md
    .git/
    foo/
        __init__.py
        __main__.py
        bar.py
```

With this structure, any Python file in the project can do `from foo import bar` to access things defined in `bar.py`.

Of course, not all Python projects follow the same structure.
Check the correct commands for running the project from its README.
