import io
import os
import sys
import tarfile
import zipfile

import requests

os.makedirs("lib", exist_ok=True)
if sys.platform == "win32":
    response = requests.get(
        "https://github.com/petasis/tkdnd/releases/download/tkdnd-release-test-v2.9.2/tkdnd-2.9.2-windows-x64.zip"
    )
    response.raise_for_status()
    zipfile.ZipFile(io.BytesIO(response.content)).extractall("lib")
elif sys.platform == "darwin":
    response = requests.get(
        "https://github.com/petasis/tkdnd/releases/download/tkdnd-release-test-v2.9.2/tkdnd-2.9.2-osx-x64.tgz"
    )
    response.raise_for_status()
    tarfile.TarFile.gzopen(None, fileobj=io.BytesIO(response.content)).extractall("lib")
else:
    raise RuntimeError("use e.g. apt-get")
