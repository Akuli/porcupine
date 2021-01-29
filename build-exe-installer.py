import argparse
import configparser
import functools
import os
import pathlib
import platform
import shutil
import struct
import subprocess
import sys

import PIL.Image

from porcupine import version_info


assert platform.system() == 'Windows', "this script must be ran on windows"

# it's possible to run a 32-bit python on a 64-bit windows, but it would
# probably screw up tkinter dll stuff... looking at help('struct'),
# struct.calcsize('P') returns the size of a pointer, which is 32 bits or 64
# bits depending on the python, and 32 bits == 4 bytes
assert not (struct.calcsize('P') == 4 and '64' in platform.machine()), (
    "this script can't be ran with 32-bit Python on a 64-bit Windows, "
    "install a 64-bit Python instead")


# info("asd") prints "build-exe-installer.py: asd"
info = functools.partial(print, sys.argv[0] + ':', file=sys.stderr, flush=True)


def get_frozen_requirements_in_a_crazy_way():
    info("Creating a temporary virtualenv and installing everything into it "
         "in order to get output from 'pip freeze' to figure out which "
         "dependencies to bundle...")
    subprocess.check_call([sys.executable, '-m', 'venv', 'temp_env'])
    try:
        subprocess.check_call([r'temp_env\Scripts\python.exe', '-m', 'pip', 'install', '-r', 'requirements.txt'])
        frozen = subprocess.check_output([r'temp_env\Scripts\python.exe', '-m', 'pip', 'freeze'])
    finally:
        shutil.rmtree('temp_env')
    return [requirement for requirement in frozen.decode('utf-8').strip().splitlines()
            if not requirement.lower().startswith('porcupine==')]


# https://pynsist.readthedocs.io/en/latest/faq.html#packaging-with-tkinter
def copy_tkinter_files():
    info("Copying tkinter files...")
    prefix = pathlib.Path(sys.prefix)
    shutil.copytree(prefix / 'tcl', 'lib')
    os.mkdir('pynsist_pkgs')
    for file in list((prefix / 'DLLs').glob('tk*.dll')) + list((prefix / 'DLLs').glob('tcl*.dll')):
        shutil.copy(file, 'pynsist_pkgs')
    shutil.copy(prefix / 'DLLs' / '_tkinter.pyd', 'pynsist_pkgs')
    shutil.copy(prefix / 'libs' / '_tkinter.lib', 'pynsist_pkgs')


def create_ico_file():
    info(r"Converting logo to .ico format...")
    PIL.Image.open(r'porcupine\images\logo-200x200.gif').save('porcupine-logo.ico')


def create_pynsist_cfg():
    info("Creating pynsist.cfg...")
    parser = configparser.ConfigParser()
    parser['Application'] = {
        'name': 'Porcupine',
        'version': 'v%d.%d.%d' % version_info,
        'entry_point': 'porcupine.__main__:main',    # setup.py copy pasta
        'icon': 'porcupine-logo.ico',
        'license_file': 'LICENSE',
    }
    parser['Python'] = {
        'version': '%d.%d.%d' % sys.version_info[:3],
    }
    parser['Include'] = {
        'pypi_wheels': '\n'.join(get_frozen_requirements_in_a_crazy_way()),
        'packages': 'tkinter\n_tkinter',
        'files': 'porcupine/images\nlib',
    }
    with open('pynsist.cfg', 'w') as file:
        parser.write(file)


def run_pynsist(python):
    info(f"Running pynsist with {python}")
    subprocess.check_call([python, '-m', 'nsist', 'pynsist.cfg'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--python', default=sys.executable)
    args = parser.parse_args()

    for path in [r'build\nsis', 'pynsist_pkgs', 'lib']:
        try:
            shutil.rmtree(path)
            info("Deleted", path)
        except FileNotFoundError:
            pass

    copy_tkinter_files()
    create_ico_file()
    create_pynsist_cfg()
    run_pynsist(args.python)
    info("All done")


if __name__ == '__main__':
    main()
