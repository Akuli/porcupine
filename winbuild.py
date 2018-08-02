import contextlib
import os
import pathlib      # is useful sometimes... although i hate it mostly
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import tkinter
import urllib.request
import zipfile

import requests


assert platform.system() == 'Windows', "this script must be ran on windows"

# looking at help('struct'), 'P' is a C type capable of holding a pointer,
# which is 32 bits on a 32-bit windows or 64 bits on a 64-bit windows, but
# struct.calcsize returns the size in bytes, so need *8 to get bits
BITS = struct.calcsize('P') * 8
assert BITS in {32, 64}


@contextlib.contextmanager
def download(url, file):
    print("Downloading %s..." % url)

    # i didn't feel like making this thing depend on requests because of this
    with urllib.request.urlopen(url) as response:
        shutil.copyfileobj(response, file)


def download_standalone_python():
    version = '%d.%d.%d' % sys.version_info[:3]

    # python.org's download links point to urls like this
    url = ('https://www.python.org/ftp/python/%s/python-%s-embed-%s.zip'
           % (version, version, ('win32' if BITS == 32 else 'amd64')))

    # the zip contains an entire python, so use a tempfile to avoid having
    # it all in RAM at once
    with tempfile.TemporaryFile() as temp_zip:
        download(url, temp_zip)
        temp_zip.seek(0)

        print(r"Extracting to winbuild\python...")
        with zipfile.ZipFile(temp_zip) as zip_object:
            zip_object.extractall(r'winbuild\python')


def unzip_stdlib():
    # i don't know why, but i got setuptools errors without extracting the
    # zip that contains the standard library
    zip_path = r'winbuild\python\python%d%d.zip' % sys.version_info[:2]
    print("Extracting %s..." % zip_path)
    with zipfile.ZipFile(zip_path, 'r') as zip_object:
        zip_object.extractall(r'winbuild\python')

    # because this fixes more errors
    print("Removing %s..." % zip_path)
    os.remove(zip_path)


def run_python(args):
    subprocess.call([r'winbuild\python\python.exe'] + args)


def run_pip(args, *, pip=('-m', 'pip')):
    run_python(list(pip) + args + [
        '--no-warn-script-location',     # pip warns about stuff not in PATH
        '--target', r'winbuild\python',  # in the python's sys.path
        '--upgrade',                     # to suppress warnings, lol
    ])


def install_pip():
    # i had some permission issues with tempfile
    with open(r'winbuild\get-pip.py', 'wb') as file:
        download('https://bootstrap.pypa.io/get-pip.py', file)

    # get-pip.py contains a copy of pip and takes the same arguments as pip
    print("Running get-pip.py...")
    run_pip([], pip=[r'winbuild\get-pip.py'])

    print("Deleting get-pip.py...")
    os.remove(r'winbuild\get-pip.py')


def install_porcupine():
    print("Installing Porcupine and dependencies...")
    run_pip(['install', '.'])


def install_tkinter():
    print("Copying tkinter files to the new python...")

    # basic pathlib... need to convert between Paths and strings a lot
    # i'm using pathlib because sys.prefix might contain a * and it would screw
    # up globbing, unless i use glob.escape
    dlldir = pathlib.Path(sys.prefix) / 'DLLs'

    # i found the files to copy by just trying to run stuff until things worked
    for file in list(dlldir.glob('tk*.dll')) + list(dlldir.glob('tcl*.dll')):
        file = str(file)
        shutil.copy(file, r'winbuild\python')

    shutil.copy(str(dlldir / '_tkinter.pyd'), r'winbuild\python')
    shutil.copytree(tkinter.__path__[0], r'winbuild\python\tkinter')

    # i got an error message that suggested this
    shutil.copytree(os.path.join(sys.prefix, 'tcl'), r'winbuild\lib')


def main():
    try:
        os.mkdir('winbuild')
    except FileExistsError:
        print("Removing old winbuild directory...")
        shutil.rmtree('winbuild')
        os.mkdir(r'winbuild')

    os.mkdir(r'winbuild\python')
    download_standalone_python()
    unzip_stdlib()
    install_pip()
    install_tkinter()
    install_porcupine()


if __name__ == '__main__':
    main()
