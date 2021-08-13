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
from porcupine import version_info as porcupine_version

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

# TODO: uninstall icon not working
print("Converting logo to .ico format")
PIL.Image.open("porcupine/images/logo-200x200.gif").save("build/porcupine-logo.ico")

print("Compiling launcher exe")
subprocess.check_call(
    ["windres", "resources.rc", "-O", "coff", "-o", "resources.res"], cwd="build/launcher"
)
subprocess.check_call(
    ["gcc.exe", "-municode", "-mwindows", "-o", "Porcupine.exe", "main.c", "resources.res"],
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

zip_object = zipfile.ZipFile(io.BytesIO(response.content))
zip_object.extractall("build/Python")

print("Moving files")
shutil.move("build/launcher/Porcupine.exe", "build/Python/Porcupine.exe")
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
    ["makensis.exe", "/DVERSION=%d.%d.%d" % porcupine_version, "installer.nsi"], cwd="build"
)

print("All done")
