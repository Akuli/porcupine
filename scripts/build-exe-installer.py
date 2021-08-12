import io
import os
import requests
import shutil
import struct
import subprocess
import sys
import tkinter
import zipfile
from pathlib import Path

import PIL.Image

# needs 64-bit windows, struct.calcsize("P") returns the size of a pointer
assert sys.platform == "win32"
assert 8*struct.calcsize("P") == 64


def copy_files():
    print("Copying files")

    if "VIRTUAL_ENV" in os.environ:
        # Could be wrong, but good enough for developing this locally
        prefix = Path(f'~/AppData/Local/Programs/Python/Python3{sys.version_info[1]}').expanduser()
    else:
        prefix = Path(sys.prefix)

    # https://pynsist.readthedocs.io/en/latest/faq.html#packaging-with-tkinter
    # We don't use pynsist because it does not allow specifying a custom pythonw.exe.
    # We need a custom pythonw.exe for the icon, lol.
    # Apparently pynsist copies pynsist_pkgs to pkgs, and nsist then installs pkgs
    shutil.copytree(prefix / "tcl", "build/lib")
    os.mkdir("build/pkgs")
    for file in list((prefix / "DLLs").glob("tk*.dll")) + list((prefix / "DLLs").glob("tcl*.dll")):
        shutil.copy(file, "build/pkgs")
    shutil.copy(prefix / "DLLs" / "_tkinter.pyd", "build/pkgs")
    shutil.copy(prefix / "libs" / "_tkinter.lib", "build/pkgs")
    shutil.copytree(tkinter.__path__[0], "build/pkgs/tkinter")

    shutil.copy("scripts/installer.nsi", "build/installer.nsi")
    shutil.copy("scripts/Porcupine.launch.pyw", "build/Porcupine.launch.pyw")
    shutil.copy("LICENSE", "build/LICENSE")


def install_pip_packages():
    print("Installing Porcupine with pip into build/pkgs")
    # TODO: delete --use-feature=in-tree-build when pip is new enough to not
    #       generate a warning without it
    subprocess.check_call(['pip', 'install', '--use-feature=in-tree-build','--target=build/pkgs', '.'])


def download_python():
    print("Downloading Python")
    # Url calculating code based on pynsist
    version = "%d.%d.%d" % sys.version_info[:3]
    filename = f'python-{version}-embed-amd64.zip'
    url = f'https://www.python.org/ftp/python/{version}/{filename}'
    print(url)

    response = requests.get(url)
    response.raise_for_status()

    zip_object = zipfile.ZipFile(io.BytesIO(response.content))
    zip_object.extractall('build/Python')


def customize_python_exe():
    print("Customizing executable icon: pythonw.exe --> Porcupine.exe")
    subprocess.check_call([
        r"C:\Program Files (x86)\Resource Hacker\ResourceHacker.exe",
        "-open", "pythonw.exe",
        "-save", "Porcupine.exe",
        "-action", "addoverwrite",
        "-res", r"..\porcupine-logo.ico",
        "-mask", "ICONGROUP,MAINICON,",
        ], cwd="build/Python")


def download_tkdnd():
    print("Downloading tkdnd")
    subprocess.check_call([sys.executable, os.path.abspath("scripts/download-tkdnd.py")], cwd="build")

    print("Ensuring that tkdnd is usable")
    root = tkinter.Tk()
    root.withdraw()
    root.tk.eval("lappend auto_path build/lib")
    root.tk.eval("package require tkdnd")
    root.destroy()


# TODO: does it really need to be included in the installer?
def create_ico_file():
    print(r"Converting logo to .ico format")
    PIL.Image.open(r"porcupine\images\logo-200x200.gif").save("build/porcupine-logo.ico")


def run_makensis():
    print("Running makensis")
    subprocess.check_call([r"C:\Program Files (x86)\NSIS\makensis.exe", "installer.nsi"], cwd="build")


def main():
    try:
        os.mkdir("build")
    except FileExistsError:
        for content in list(Path("build").glob("*")):
            if content.is_file():
                content.unlink()
            else:
                shutil.rmtree(content)

    copy_files()
    install_pip_packages()
    download_python()
    create_ico_file()
    customize_python_exe()
    download_tkdnd()
    run_makensis()

    print("All done")


if __name__ == "__main__":
    main()
