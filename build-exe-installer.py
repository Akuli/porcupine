# FIXME: this contains copy/pasta from setup.py
import configparser
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys


assert platform.system() == 'Windows', "this script must be ran on windows"


# setup.py copy pasta
def get_requirements():
    with open('requirements.txt', 'r') as file:
        for line in map(str.strip, file):
            if (not line.startswith('#')) and line:
                yield line


# setup.py copy pasta
def find_metadata():
    with open(os.path.join('porcupine', '__init__.py')) as file:
        content = file.read()

    result = dict(re.findall(
        r'''^__(author|copyright|license)__ = ['"](.*)['"]$''',
        content, re.MULTILINE))
    assert result.keys() == {'author', 'copyright', 'license'}, result

    # version is defined like this: __version__ = '%d.%d.%d' % version_info
    version_info = re.search(r'^version_info = \((\d+), (\d+), (\d+)\)',
                             content, re.MULTILINE).groups()
    result['version'] = '%s.%s.%s' % version_info

    return result


def get_frozen_requirements_in_a_crazy_way():
    subprocess.check_call([sys.executable, '-m', 'venv', 'temp_env'])

    try:
        subprocess.check_call([
            r'temp_env\Scripts\python.exe', '-m',
            'pip', 'install', '-r', 'requirements.txt'])
        frozen = subprocess.check_output([
            r'temp_env\Scripts\python.exe', '-m', 'pip', 'freeze'
        ]).decode('utf-8').strip().splitlines()
    finally:
        shutil.rmtree('temp_env')

    return [requirement for requirement in frozen
            if not requirement.lower().startswith('porcupine==')]


def mkdir_empty(path):
    try:
        os.mkdir(path)
    except FileExistsError:
        shutil.rmtree(path)
        os.mkdir(path)


# https://pynsist.readthedocs.io/en/latest/faq.html#packaging-with-tkinter
def copy_tkinter_files():
    shutil.copytree(os.path.join(sys.prefix, 'tcl'), 'lib')

    # basic pathlib... need to convert between Paths and strings a lot
    # i'm using pathlib because sys.prefix might contain a * and it would screw
    # up globbing, unless i use glob.escape
    mkdir_empty('pynsist_pkgs')
    dlldir = pathlib.Path(sys.prefix) / 'DLLs'
    for file in list(dlldir.glob('tk*.dll')) + list(dlldir.glob('tcl*.dll')):
        file = str(file)
        shutil.copy(file, 'pynsist_pkgs')

    shutil.copy(str(dlldir / '_tkinter.pyd'), 'pynsist_pkgs')
    shutil.copy(os.path.join(sys.prefix, 'libs', '_tkinter.lib'),
                'pynsist_pkgs')


def create_pynsist_cfg():
    parser = configparser.ConfigParser()
    parser['Application'] = {
        'name': 'Porcupine',
        'version': find_metadata()['version'],
        'entry_point': 'porcupine.__main__:main',    # setup.py copy pasta
        # TODO: icon
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


def run_pynsist():
    subprocess.check_call([sys.executable, '-m', 'nsist', 'pynsist.cfg'])


def main():
    try:
        shutil.rmtree(r'build\nsis')
    except FileNotFoundError:
        pass

    create_pynsist_cfg()
    copy_tkinter_files()
    run_pynsist()


if __name__ == '__main__':
    main()
