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


print("Copying files")

if "VIRTUAL_ENV" in os.environ:
    # Could be wrong, but good enough for developing this locally
    prefix = Path(f"~/AppData/Local/Programs/Python/Python3{sys.version_info[1]}").expanduser()
else:
    prefix = Path(sys.prefix)

# https://pynsist.readthedocs.io/en/latest/faq.html#packaging-with-tkinter
# We don't use pynsist because it does not allow specifying a custom pythonw.exe.
# We need a custom pythonw.exe for the icon, lol.
# pynsist copies pynsist_pkgs to pkgs, and nsist then installs pkgs
shutil.copytree(prefix / "tcl", "build/lib")
os.mkdir("build/pkgs")
for file in list((prefix / "DLLs").glob("tk*.dll")) + list((prefix / "DLLs").glob("tcl*.dll")):
    shutil.copy(file, "build/pkgs")
shutil.copy(prefix / "DLLs" / "_tkinter.pyd", "build/pkgs")
shutil.copy(prefix / "libs" / "_tkinter.lib", "build/pkgs")
shutil.copytree(tkinter.__path__[0], "build/pkgs/tkinter")

shutil.copy("scripts/installer.nsi", "build/installer.nsi")
shutil.copy("LICENSE", "build/LICENSE")
shutil.copytree("launcher", "build/launcher")

metadata_file = Path("build/launcher/metadata.rc")
print(f"Editing version info into {metadata_file}")
metadata_file.write_text(
    metadata_file.read_text().replace("PORCUPINE_VERSION", f'"{porcupine_version}"')
)

# TODO: uninstall icon not working
print("Converting logo to .ico format")
PIL.Image.open("porcupine/images/logo-200x200.gif").save("build/porcupine-logo.ico")

# If you can't get a C compiler to work (with windres):
#   1. Download a Porcupine installer from GitHub and install Porcupine
#   2. Copy C:\Users\YourName\AppData\Local\Programs\Porcupine\Porcupine\Porcupine.exe
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

print("Installing Porcupine into build/pkgs with pip")
# TODO: delete --use-feature=in-tree-build when pip is new enough to not make warning without it
subprocess.check_call(["pip", "install", "--use-feature=in-tree-build", "--target=build/pkgs", "."])

print("Downloading Python")
# Uses same url as pynsist
version = "%d.%d.%d" % sys.version_info[:3]
filename = f"python-{version}-embed-amd64.zip"
url = f"https://www.python.org/ftp/python/{version}/{filename}"
print(url)

response = requests.get(url)
response.raise_for_status()

# nsis script installs python like this
#
#   C:\Users\Akuli\AppData\Local
#   `-- Porcupine
#       |-- lib
#       |-- pkgs
#       `-- Porcupine (*)
#           |-- Porcupine.exe
#           |-- python.exe
#           |-- python3.dll
#           `-- pythonw.exe
#
# Porcupine.exe must be in same directory with python3.dll.
# python3.dll must be in the same directory with python.exe.
# The name of directory (*) shows up in "Open file" dialog.
# If Porcupine.exe is not nested in the directory, it shows "Porcupine.exe".
# This is why there is Porcupine directory containign Python nested inside another Porcupine directory.
zipfile.ZipFile(io.BytesIO(response.content)).extractall("build/Porcupine")

print("Moving files")
shutil.move("build/launcher/Porcupine.exe", "build/Porcupine/Porcupine.exe")
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
