"""Handy plugin installer.

Here's an example layout for this plugin installer:

    |-- stuff/
    |   |-- nice_plugin.py
    |   `-- another_plugin/
    |       |-- __init__.py
    |       `-- thingy.py
    `-- plugin_paths.txt

Here's plugin_paths.txt:

    stuff/nice_plugin.py
    stuff/another_plugin

The file paths are relative to the plugin_paths.txt file, and they
should always use / as the path separator.
"""
# some of this code uses a hard-coded '/' instead of os.path because the
# zipfile module uses '/' as a path separator on all platforms

import collections
import io
import os
import posixpath
import re
import shutil
import sys
import tempfile
import textwrap
import zipfile

import requests

import porcupine.plugins


def copy(source, destdir):
    print("Copying %r to %r..." % (source, destdir))
    if os.path.isdir(source):
        dest = os.path.join(destdir, os.path.basename(source))
        shutil.copytree(source, dest)
    else:
        # shutil.copy() allows the destination to be a directory
        shutil.copy(source, destdir)


# return two-tuple of (file, plugin_name) where file is an argument for
# zipfile.ZipFile and plugin_name would be 'nice_thingy' or
# 'another_plugin' in the docstring example
def download_plugin(spec):
    name = None

    if spec.isidentifier():
        # e.g. porcu --install-plugin tetris
        url = 'https://github.com/%s/porcupine/archive/v%s.zip' % (
            porcupine.__author__, porcupine.__version__)
        name = spec
    elif spec == '-':
        # stdin
        return (sys.stdin.read(), None)
    elif spec.startswith(('http://', 'https://')):
        # e.g. https://example.org/porcuplugins.zip
        url = spec
    elif os.path.isfile(spec):
        # e.g. porcuplugins.zip, SomePath/porcuplugins.zip
        # can't rely on checking .zip extension because extensions are
        # not required and someone's github username might end with .zip
        return (spec, None)
    elif spec.count('/') == 1:
        # e.g. SomeGithubUser/porcuplugins
        # hopefully there's not a file named SomeGithubUser/porcuplugins...
        user, repo = spec.split('/')
        url = 'https://github.com/%s/%s/archive/master.zip' % (user, repo)
    else:
        sys.exit("Sorry, I don't know how to install %r :/" % spec)

    print("Downloading %r..." % url)
    result = requests.get(url).content
    if result.strip() == b'Not Found':
        sys.exit("Expected a zip file, got 'Not Found' O_o")
    return (io.BytesIO(result), name)


def install_plugin(file, plugin_name):
    print("Reading the zip file...")
    with zipfile.ZipFile(file) as the_zip:

        path_files = [name for name in the_zip.namelist()
                      if posixpath.basename(name) == 'plugin_paths.txt']
        if not path_files:
            sys.exit("Cannot find plugin_paths.txt :(")
        if len(path_files) > 1:
            sys.exit("Found multiple plugin_paths.txt files 0_o " +
                     ", ".join(path_files))
        path_file = path_files[0]

        paths = {}      # {plugin_name: path_in_the_zip}
        with the_zip.open(path_file) as f:
            for line in f:
                path = line.decode('utf-8').strip().rstrip('/')
                if path:
                    name = posixpath.splitext(posixpath.basename(path))[0]
                    if name in paths:
                        sys.exit("%r contains multiple %r plugins 0_o"
                                 % (path_file, name))
                    paths[name] = path

        if not paths:
            sys.exit("%r is empty!" % path_file)

        if plugin_name is None:
            if len(paths) == 1:
                (plugin_name,) = paths.keys()
            else:
                print("The zip file contains multiple plugins:")
                for line in textwrap.wrap(' '.join(paths)):
                    print('  ', line)

                while True:
                    plugin_name = input("Choose one of these plugins: ")
                    if plugin_name in paths:
                        break
                    print("Try again.")
        if plugin_name not in paths:
            sys.exit("Cannot find %r, but there are %d other plugins 0_o"
                     % (plugin_name, len(paths)))

        with tempfile.TemporaryDirectory() as tempdir:
            print("Extracting %r to %r..." % (paths[plugin_name], tempdir))
            extracted = the_zip.extract(paths[plugin_name], tempdir)
            copy(extracted, porcupine.plugins.__path__[0])

            print("Cleaning up...")

    print("Done!")


install_plugin(*download_plugin(*sys.argv[1:]))
