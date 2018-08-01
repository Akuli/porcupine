"""Installs, updates and uninstalls plugins."""

import argparse
import configparser
import io
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

import requests

from porcupine import plugins, pluginloader


USER_PLUGIN_DIR = plugins.__path__[0]


class PluginError(Exception):
    """These should be displayed to the user without full traceback."""


def _parse_spec(spec, *, user_and_repo_required=True):
    """Parses a 'user/repo/plugin_name' string.

    This returns a string-tuple like (user, repo, plugin_name) or throws
    PluginError. If user_and_repo_required is False, also accepts
    'plugin_name', returning (None, None, plugin_name).
    """
    if user_and_repo_required or '/' in spec:
        try:
            user, repo, plugin_name = spec.split('/')
            if not (user and repo and plugin_name):
                raise ValueError
        except ValueError:
            message = ("%r doesn't look like a valid user/repo/pluginname "
                       "specification" % spec)
            if not user_and_repo_required:
                message += " or a plugin name"
            raise PluginError(message)

    else:
        user = None
        repo = None
        plugin_name = spec

    if plugin_name.startswith('_') or not plugin_name.isidentifier():
        raise PluginError("%r is not a valid plugin name" % plugin_name)

    return (user, repo, plugin_name)


def install(spec, *, reinstall=False):
    """Download a plugin from GitHub and install it.

    The spec should be a 'user/repo/plugin_name' string. PluginError is thrown
    on errors that should be caught and printed to the user without traceback.

    If reinstalling is True, any existing installation of the plugin is
    removed first.
    """
    try:
        user, repo, plugin_name = spec.split('/')
        if not (user and repo and plugin_name):
            raise ValueError
    except ValueError:
        raise PluginError(
            "%r doesn't look like a valid user/repo/pluginname specification"
            % spec)

    issue_url = 'https://github.com/%s/%s/issues' % (user, repo)

    if plugin_name in pluginloader.find_plugins():
        if not reinstall:
            raise PluginError("a plugin named %r is already installed, "
                              "uninstall it before installing it again"
                              % plugin_name)

        print("A plugin named %r is already installed, removing it now..."
              % plugin_name)
        remove(plugin_name)

    # 'git clone --depth=1' could be used, except that this must work if git
    # is not installed, github has a "Download ZIP" button that gives URLs
    # like these
    #zip_url = 'https://github.com/%s/%s/archive/master.zip' % (user, repo)
    zip_url = 'https://github.com/%s/%s/archive/test.zip' % (user, repo)

    # the whole zip must fit in ram, but that's ok imo, and hard to avoid, the
    # best alternative would be a temporary file because zipfile.ZipFile wants
    # to seek the file, and a file-like HTTP response object won't do
    print("Downloading %s..." % zip_url)
    response = requests.get(zip_url)
    response.raise_for_status()
    zip_data = response.content
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zip:

        # everything is in a subfolder named <repo>-master/
        #subfolder = repo + '-master'
        subfolder = repo + '-test'
        assert (subfolder + '/') in zip.namelist()

        # zip files use '/' as separator, that's why no os.path
        print("Reading porcuplugins.ini...")
        try:
            inifile = zip.open(subfolder + '/porcuplugins.ini')
        except KeyError:  # yes, it raises KeyError
            raise PluginError("porcuplugins.ini cannot be read, are you sure "
                              "that this repository contains plugins?"
                              % (plugin_name, issue_url))

        parser = configparser.ConfigParser()
        with inifile:
            # i can't get zip.open() to return text files
            inifile = io.TextIOWrapper(inifile, encoding='utf-8')

            # no exception handling here because errors SHOULD be rare here
            parser.read_file(inifile)

        try:
            section = dict(parser[plugin_name])
        except KeyError:
            raise PluginError("%s/%s doesn't contain a plugin named %r"
                              % (user, repo, plugin_name))

        if 'path' not in section:
            raise PluginError("the porcuplugins.ini in %s/%s doesn't define a "
                              "path in [%s], please report to %s"
                              % (user, repo, plugin_name, issue_url))

        pip_depends = section.get('pip_dependencies', '').split()
        if pip_depends:
            print("Installing dependencies with pip...")
            status = subprocess.call(
                [sys.executable, '-m', 'pip', 'install', '--user'] +
                section['pip_dependencies'].split())
            if status != 0:
                raise PluginError("pip failed with status %d" % status)

        # directory names of zip files seem to always end with /
        names = zip.namelist()
        path = subfolder + '/' + section['path']

        if path not in names and (path + '/') in names:
            path += '/'
        if path not in names:
            raise PluginError(
                "no file named %r found in the zip, report to %s/%s"
                % (section['path'], user, repo))

        if path.endswith('/'):
            going_to_extract = [member for member in zip.namelist()
                                if member.startswith(path)]
        else:
            going_to_extract = [path]

        # there seems to be no way to extract without the <repo>-master nesting
        with tempfile.TemporaryDirectory() as tempdir:
            print("Extracting the zip file to %s..." % tempdir)
            zip.extractall(tempdir, members=going_to_extract)

            fixed_path = path.replace('/', os.sep)
            old_path = os.path.join(tempdir, fixed_path)
            new_path = os.path.join(USER_PLUGIN_DIR,
                                    os.path.basename(fixed_path))

            print("Copying %s to %s..." % (old_path, new_path))
            if os.path.isdir(old_path):
                shutil.copytree(old_path, new_path)
            else:
                shutil.copy(old_path, new_path)

            # the with block ends here
            print("Deleting %s..." % tempdir)

    print()
    print("Done! Restart Porcupine to use the %s plugin." % plugin_name)


def _wanna_continue():
    while True:
        answer = input("Do you want to continue? [Y/n] ").lower().strip()
        if answer == 'y' or not answer:
            return
        if answer == 'n':
            raise PluginError("aborted")


def remove(plugin_spec):
    *user_and_repo_junk, plugin_name = _parse_spec(plugin_spec)
    dir_path = os.path.join(USER_PLUGIN_DIR, plugin_name)
    file_path = dir_path + '.py'

    if os.path.isfile(file_path):
        print("This file will be deleted:\n  %s" % file_path)
        _wanna_continue()
        os.remove(file_path)
    elif os.path.isdir(dir_path):
        print("This directory and everything in it will be deleted:\n  %s"
              % dir_path)
        _wanna_continue()
        shutil.rmtree(dir_path)
    else:
        # can't do it
        if plugin_name not in pluginloader.find_plugins():
            raise PluginError("the %s plugin is not installed" % plugin_name)
        raise PluginError(
            "the %s plugin cannot be uninstalled, it probably came with "
            "Porcupine or it was installed without porcuplugin"
            % plugin_name)

    print()
    print("Done!")


_DESCRIPTION = """
This is a program for downloading installing Porcupine plugins to the user-wide
Porcupine plugin directory. Your plugin directory is:

    %s

There are examples of using this tool at the end of this help message. This
tool lets you install plugins created by anyone, but here are some plugins I
have made for starters:

    https://github.com/Akuli/porcupine/tree/master/more_plugins
""" % USER_PLUGIN_DIR

_EPILOG = r"""
Examples:
  %(prog)s install Akuli/porcupine/tetris  # install my tetris plugin
  %(prog)s remove tetris                   # ok, back to work now
"""


def main():
    parser = argparse.ArgumentParser(
        description=_DESCRIPTION, epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        'subcommand', choices=['install', 'remove', 'reinstall'],
        help="what to do, see examples below")
    parser.add_argument(
        'plugin_spec', help=(
            "user/repo/pluginname where user and repo are a GitHub user name "
            "and repository name, and pluginname is the name of a plugin "
            "hosted in that repository. For example, Akuli/porcupine/tetris "
            "means the tetris plugin you can find in my porcupine "
            "repository: https://github.com/Akuli/porcupine"))
    args = parser.parse_args()

    try:
        if subcommand == 'install':
            install(args.plugin_spec)
        elif subcommand == 'reinstall':
            install(args.plugin_spec, reinstall=True)
        elif subcommand == 'remove':
            remove(args.plugin_spec)
        else:
            raise ValueError("oh no")
    except PluginError as e:
        sys.exit("%s: %s" % (sys.argv[0], str(e)))


if __name__ == '__main__':
    main()
