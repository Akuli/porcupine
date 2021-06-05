import configparser
import functools
import os
import pathlib
import platform
import shutil
import struct
import subprocess
import sys
import tkinter

import PIL.Image

assert sys.platform == "win32", "this script must be ran on windows"

# it's possible to run a 32-bit python on a 64-bit windows, but it would
# probably screw up tkinter dll stuff... looking at help('struct'),
# struct.calcsize('P') returns the size of a pointer, which is 32 bits or 64
# bits depending on the python, and 32 bits == 4 bytes
assert not (struct.calcsize("P") == 4 and "64" in platform.machine()), (
    "this script can't be ran with 32-bit Python on a 64-bit Windows, "
    "install a 64-bit Python instead"
)

[this_script_name, porcupine_version] = sys.argv

# info("asd") prints "build-exe-installer.py: asd"
info = functools.partial(print, this_script_name + ":", file=sys.stderr, flush=True)


def get_frozen_requirements_in_a_crazy_way():
    info(
        "Creating a temporary virtualenv and installing everything into it "
        "in order to get output from 'pip freeze' to figure out which "
        "dependencies to bundle..."
    )
    subprocess.check_call([sys.executable, "-m", "venv", "temp_env"])
    try:
        subprocess.check_call(
            [r"temp_env\Scripts\python.exe", "-m", "pip", "install", "-r", "requirements.txt"]
        )
        frozen = subprocess.check_output([r"temp_env\Scripts\python.exe", "-m", "pip", "freeze"])
    finally:
        shutil.rmtree("temp_env")
    return frozen.decode("utf-8").strip().splitlines()


# https://pynsist.readthedocs.io/en/latest/faq.html#packaging-with-tkinter
def copy_tkinter_files():
    info("Copying tkinter files...")
    prefix = pathlib.Path(sys.prefix)
    shutil.copytree(prefix / "tcl", "lib")
    os.mkdir("pynsist_pkgs")
    for file in list((prefix / "DLLs").glob("tk*.dll")) + list((prefix / "DLLs").glob("tcl*.dll")):
        shutil.copy(file, "pynsist_pkgs")
    shutil.copy(prefix / "DLLs" / "_tkinter.pyd", "pynsist_pkgs")
    shutil.copy(prefix / "libs" / "_tkinter.lib", "pynsist_pkgs")


def download_tkdnd():
    info("Downloading tkdnd")
    subprocess.check_call(
        [sys.executable, "scripts/download-tkdnd.py"], cwd=pathlib.Path(__file__).parent.parent
    )

    info("Ensuring that tkdnd is usable")
    root = tkinter.Tk()
    root.withdraw()
    root.tk.eval("lappend auto_path lib")
    root.tk.eval("package require tkdnd")
    root.destroy()


def create_ico_file():
    info(r"Converting logo to .ico format...")
    PIL.Image.open(r"porcupine\images\logo-200x200.gif").save("porcupine-logo.ico")


def create_pynsist_cfg():
    info("Creating pynsist.cfg...")

    deps_from_pypi_wheels = []
    deps_without_pypi_wheels = ["tkinter", "_tkinter"]
    for dependency in get_frozen_requirements_in_a_crazy_way():
        name, version = dependency.split("==")
        if name.lower() == "porcupine":
            pass
        elif name.lower() in {"ttkthemes", "black"}:
            deps_without_pypi_wheels.append(name)
        else:
            deps_from_pypi_wheels.append(dependency)

    parser = configparser.ConfigParser()
    parser["Application"] = {
        "name": "Porcupine",
        "version": porcupine_version,
        "entry_point": "porcupine.__main__:main",  # setup.py copy pasta
        "icon": "porcupine-logo.ico",
        "license_file": "LICENSE",
    }
    parser["Python"] = {"version": "%d.%d.%d" % sys.version_info[:3]}
    parser["Include"] = {
        "pypi_wheels": "\n".join(deps_from_pypi_wheels),
        "packages": "\n".join(deps_without_pypi_wheels),
        "files": "porcupine/images\nlib",
    }

    parser.write(sys.stderr)
    sys.stderr.flush()

    with open("pynsist.cfg", "w") as file:
        parser.write(file)


def run_pynsist():
    subprocess.check_call([sys.executable, "-m", "nsist", "pynsist.cfg"])


def main():
    copy_tkinter_files()
    download_tkdnd()
    create_ico_file()
    create_pynsist_cfg()
    run_pynsist()
    info("All done")


if __name__ == "__main__":
    main()
