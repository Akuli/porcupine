import hashlib
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
import toml

sys.path.append("")  # import from current working directory
from porcupine import __version__ as porcupine_version

# needs 64-bit windows, struct.calcsize("P") returns the size of a pointer
assert sys.platform == "win32"
assert 8 * struct.calcsize("P") == 64


try:
    os.mkdir("build")
    print("Created directory: build")
except FileExistsError:
    print("Found existing build directory, deleting contents")
    for path in list(Path("build").glob("*")):
        if path.is_file():
            path.unlink()
        else:
            shutil.rmtree(path)


print("Downloading Python")
# Uses same url as pynsist
version = "%d.%d.%d" % sys.version_info[:3]
filename = f"python-{version}-embed-amd64.zip"
url = f"https://www.python.org/ftp/python/{version}/{filename}"
print(url)

response = requests.get(url)
response.raise_for_status()
zipfile.ZipFile(io.BytesIO(response.content)).extractall("build/python-first")

print("Downloading NSIS")
url = "https://downloads.sourceforge.net/project/nsis/NSIS%203/3.08/nsis-3.08.zip"
print(url)
response = requests.get(url)
response.raise_for_status()
zip_hash = hashlib.sha256(response.content).hexdigest()
assert zip_hash == "1bb9fc85ee5b220d3869325dbb9d191dfe6537070f641c30fbb275c97051fd0c"
zipfile.ZipFile(io.BytesIO(response.content)).extractall("build")


print("Copying files")

if "VIRTUAL_ENV" in os.environ:
    # Could be wrong, but good enough for developing this locally
    prefix = Path(f"~/AppData/Local/Programs/Python/Python3{sys.version_info[1]}").expanduser()
else:
    prefix = Path(sys.prefix)

# When installing, python-first and python-second get merged together, but a minimal
# python is needed to fail setup early if it can't run.
os.mkdir("build/python-second")

# https://pynsist.readthedocs.io/en/latest/faq.html#packaging-with-tkinter
# We don't use pynsist because it does not allow specifying a custom executable.
# We have a custom Porcupine.exe launcher which has the custom icon and can be called
# with no arguments to launch Porcupine.
# I couldn't get python to import from anywhere else than from Python directory,
# so no separate pynsist_pkgs.
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

# If you can't get a C compiler to work, you can install an older version of Porcupine and copy
# its Porcupine.exe to launcher/Porcupine.exe
if os.path.exists("build/launcher/Porcupine.exe"):
    print("Found launcher/Porcupine.exe, no C compiler needed")
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
            "clang.exe",
            "-municode",
            "-o",
            "Porcupine.exe",
            "main.c",
            "icon.res",
            "metadata.res",
            "-luser32",
            "-Wl,--subsystem,windows",  # https://stackoverflow.com/a/37409970
        ],
        cwd="build/launcher",
    )

print("Installing Porcupine into build/python-second with pip")
subprocess.check_call(
    [
        "pip",
        "install",
        "--target=build/python-second",
        ".",
        "setuptools",  # pyls needs pkg_resources from setuptools, don't know why need explicitly
    ]
)

print("Deleting __pycache__ directories")
for path in list(Path("build/python-second").rglob("__pycache__")):
    print(path)
    shutil.rmtree(path)

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

print("Finding supported file extensions")
extensions = [
    pattern.lstrip("*")
    for filetype in toml.load("porcupine/default_filetypes.toml").values()
    for pattern in filetype["filename_patterns"]
    if pattern.startswith("*.") and pattern.count("*") == 1 and "," not in pattern
]
print(extensions)

makensis = os.path.abspath("build/nsis-3.08/makensis.exe")
print(f"Running {makensis}")
subprocess.check_call(
    [
        makensis,
        "/DVERSION=" + porcupine_version,
        "/DEXTENSIONS=" + ",".join(extensions),
        "installer.nsi",
    ],
    cwd="build",
)

print("All done")
