import contextlib
import glob
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
import venv
import zipfile

import porcupine


assert platform.system() == 'Windows', "this script must be ran on windows"

# looking at help('struct'), 'P' is a C type capable of holding a pointer,
# which is 32 bits on a 32-bit windows or 64 bits on a 64-bit windows, but
# struct.calcsize returns the size in bytes, so need *8 to get bits
BITS = struct.calcsize('P') * 8
assert BITS in {32, 64}


INNO_SETUP_COMPILER = r"C:\Program Files\Inno Setup 5\ISCC.exe"
assert os.path.exists(INNO_SETUP_COMPILER), (
    "Inno Setup is not installed, or it has been installed to an unusual "
    "location and " + __file__ + " needs to be updated")


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

        print(r"Extracting to windows-build\python...")
        os.mkdir(r'windows-build\python')
        with zipfile.ZipFile(temp_zip) as zip_object:
            zip_object.extractall(r'windows-build\python')


def unzip_stdlib():
    # i don't know why, but i got setuptools errors without extracting the
    # zip that contains the standard library
    [zip_path] = glob.glob(r'windows-build\python\python*.zip')
    print("Extracting %s..." % zip_path)
    with zipfile.ZipFile(zip_path, 'r') as zip_object:
        zip_object.extractall(r'windows-build\python')

    # because this fixes more errors
    print("Removing %s..." % zip_path)
    os.remove(zip_path)


def run_python(args, *, python=r'windows-build\python\python.exe'):
    subprocess.check_call([python] + args)


def run_pip(args, *, pip=('-m', 'pip')):
    run_python(list(pip) + args + [
        '--no-warn-script-location',          # no warn about stuff not in PATH
        '--target', r'windows-build\python',  # is in the python's sys.path
        '--upgrade',                          # to suppress warnings, lol
    ])


def install_pip():
    # i had some permission issues with tempfile
    with open(r'windows-build\get-pip.py', 'wb') as file:
        download('https://bootstrap.pypa.io/get-pip.py', file)

    # get-pip.py contains a copy of pip and takes the same arguments as pip
    print("Running get-pip.py...")
    run_pip([], pip=[r'windows-build\get-pip.py'])

    print("Deleting get-pip.py...")
    os.remove(r'windows-build\get-pip.py')


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
        shutil.copy(file, r'windows-build\python')

    shutil.copy(str(dlldir / '_tkinter.pyd'), r'windows-build\python')
    shutil.copytree(tkinter.__path__[0], r'windows-build\python\tkinter')

    # i got an error message that suggested this
    shutil.copytree(os.path.join(sys.prefix, 'tcl'), r'windows-build\lib')


def run_tests():
    print("Installing virtualenv temporarily...")
    shutil.copytree(venv.__path__[0], r'windows-build\python\venv')

    print("Creating a virtual env for tests...")
    run_python(['-m', 'venv', r'windows-build\env'])

    print("Installing pytest to the virtual env...")
    run_python(['-m', 'pip', 'install', 'pytest'],
               python=r'windows-build\env\Scripts\python.exe')

    print("Running pytest...")
    run_python(['-m', 'pytest'],
               python=r'windows-build\env\Scripts\python.exe')

    print("Deleting temporary files...")
    shutil.rmtree(r'windows-build\env')
    shutil.rmtree(r'windows-build\python\venv')


def delete_pycaches():
    print("Deleting Python cache files...")
    for root, dirs, files in os.walk(r'windows-build\python'):
        if '__pycache__' in dirs:
            shutil.rmtree(os.path.join(root, '__pycache__'))
            dirs.remove('__pycache__')   # don't try to do anything to it


def create_setup_exe():
    with open('innosetup.iss', 'r') as template:
        with open('innosetup-temp.iss', 'w') as innosetup:
            for line in template:
                if line.startswith('#define PorcupineVersion'):
                    innosetup.write('#define PorcupineVersion "%d.%d.%d"\n'
                                    % porcupine.version_info)
                else:
                    innosetup.write(line)

    subprocess.check_call([INNO_SETUP_COMPILER,
                           'innosetup-temp.iss'])


def main():
    try:
        os.mkdir('windows-build')
    except FileExistsError:
        print("Removing old windows-build directory...")
        shutil.rmtree('windows-build')
        os.mkdir('windows-build')

    download_standalone_python()
    unzip_stdlib()
    install_pip()
    install_tkinter()
    install_porcupine()
    run_tests()

    delete_pycaches()
    create_setup_exe()


if __name__ == '__main__':
    main()
