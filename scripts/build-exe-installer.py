import io
import os
import shutil
import struct
import subprocess
import sys
import tkinter
import zipfile
from pathlib import Path

import PIL.Image
import requests

sys.path.append("")  # import from current working directory
from porcupine import version_info as version_tuple

porcupine_version = "%d.%d.%d" % version_tuple

# needs 64-bit windows, struct.calcsize("P") returns the size of a pointer
assert sys.platform == "win32"
assert 8 * struct.calcsize("P") == 64


try:
    os.mkdir("build")
except FileExistsError:
    print("Found existing build directory, deleting contents")
    for content in list(Path("build").glob("*")):
        if content.is_file():
            content.unlink()
        else:
            shutil.rmtree(content)


print("Downloading Python")
# Uses same url as pynsist
version = "%d.%d.%d" % sys.version_info[:3]
filename = f"python-{version}-embed-amd64.zip"
url = f"https://www.python.org/ftp/python/{version}/{filename}"
print(url)

response = requests.get(url)
response.raise_for_status()
zipfile.ZipFile(io.BytesIO(response.content)).extractall("build/python-first")

print("Copying files")

if "VIRTUAL_ENV" in os.environ:
    # Could be wrong, but good enough for developing this locally
    prefix = Path(f"~/AppData/Local/Programs/Python/Python3{sys.version_info[1]}").expanduser()
else:
    prefix = Path(sys.prefix)

# https://pynsist.readthedocs.io/en/latest/faq.html#packaging-with-tkinter
#
# We don't use pynsist because it does not allow specifying a custom executable.
#
# We have a custom Porcupine.exe launcher which has the custom icon and can be called
# with no arguments to launch Porcupine.
#
# I couldn't get python to import from anywhere else than from Python directory,
# so no separate pynsist_pkgs.
#
# When installing, python and python-libs get merged together, but a minimal
# python is needed to fail setup early if it can't run.
os.mkdir("build/python-second")
shutil.copytree(prefix / "tcl", "build/lib")
for file in [*(prefix / "DLLs").glob("tk*.dll"), *(prefix / "DLLs").glob("tcl*.dll")]:
    shutil.copy(file, "build/python-second")
shutil.copy(prefix / "DLLs" / "_tkinter.pyd", "build/python-second")
shutil.copy(prefix / "libs" / "_tkinter.lib", "build/python-second")
shutil.copytree(tkinter.__path__[0], "build/python-second/tkinter")

shutil.copy("scripts/installer.nsi", "build/installer.nsi")
shutil.copy("LICENSE", "build/LICENSE")
shutil.copytree("launcher", "build/launcher")

# I tried to give -D option to preprocessor, didn't work
metadata_file = Path("build/launcher/metadata.rc")
print(f"Editing version info into {metadata_file}")
metadata_file.write_text(
    metadata_file.read_text().replace("PORCUPINE_VERSION", f'"{porcupine_version}"')
)

print("Converting logo to .ico format")
PIL.Image.open("porcupine/images/logo-200x200.gif").save("build/porcupine-logo.ico")

# If you can't get a C compiler to work (with windres):
#   1. Download a Porcupine installer from GitHub and install Porcupine
#   2. Copy C:\Users\YourName\AppData\Local\Programs\Porcupine\Python\Porcupine.exe
#      to where you cloned Porcupine
#   3. Uninstall Porcupine
if os.path.exists("Porcupine.exe"):
    print("Porcupine.exe found, no C compiler needed")
    shutil.copy("Porcupine.exe", "build/launcher/")
else:
    print("Porcupine.exe was not found, compiling")
    subprocess.check_call(
        ["windres", "icon.rc", "-O", "coff", "-o", "icon.res"], cwd="build/launcher"
    )
    subprocess.check_call(
        ["windres", "metadata.rc", "-O", "coff", "-o", "metadata.res"], cwd="build/launcher"
    )
    subprocess.check_call(
        [
            "gcc.exe",
            "-municode",
            "-mwindows",
            "-o",
            "Porcupine.exe",
            "main.c",
            "icon.res",
            "metadata.res",
        ],
        cwd="build/launcher",
    )

print("Installing Porcupine into build/python-second with pip")
# pyls needs pkg_resources from setuptools, don't know why it doesn't install by default
# TODO: delete --use-feature=in-tree-build when pip is new enough to not make warning without it
subprocess.check_call(
    ["pip", "install", "--use-feature=in-tree-build", "--target=build/python-second", ".", "setuptools"]
)

print("Moving files")
shutil.move("build/launcher/Porcupine.exe", "build/python-second/Porcupine.exe")
shutil.move("build/launcher/launch.pyw", "build/launch.pyw")

print("Downloading tkdnd")
subprocess.check_call([sys.executable, os.path.abspath("scripts/download-tkdnd.py")], cwd="build")

print("Ensuring that tkdnd is usable")
root = tkinter.Tk()
root.withdraw()
root.tk.eval("lappend auto_path build/lib")
root.tk.eval("package require tkdnd")
root.destroy()

print("Running makensis")
subprocess.check_call(
    ["makensis.exe", f"/DVERSION={porcupine_version}", "installer.nsi"], cwd="build"
)

print("All done")
