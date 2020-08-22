import os
import re
import subprocess
import sys

import porcupine


def run_porcupine(args, expected_exit_status):
    process = subprocess.Popen(
        [sys.executable, '-m', 'porcupine'] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output, junk = process.communicate()

    assert process.returncode == expected_exit_status
    return output.decode('ascii').replace(r'\r\n', '\n')


def test_version():
    assert run_porcupine(['--version'], 0) == f'Porcupine {porcupine.__version__}\n'


def test_bad_without_plugins_argument():
    output = run_porcupine(['--without-plugins=asdf'], 2)
    assert 'usage:' in output
    assert "--without-plugins: no plugin named 'asdf'" in output


def test_print_plugindir():
    output = run_porcupine(['--print-plugindir'], 0)
    match = re.fullmatch(r'You can install plugins here:\n\n +(.+)\n\n', output)
    assert match is not None
    assert os.path.isdir(match.group(1))
