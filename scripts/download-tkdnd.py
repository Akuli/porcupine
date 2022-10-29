import hashlib
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
    sha = hashlib.sha256(response.content).hexdigest()
    assert sha == "d78007d93d8886629554422de2e89f64842ac9994d226eab7732cc4b59d1feea"
    zipfile.ZipFile(io.BytesIO(response.content)).extractall("lib")
elif sys.platform == "darwin":
    response = requests.get(
        "https://github.com/petasis/tkdnd/releases/download/tkdnd-release-test-v2.9.2/tkdnd-2.9.2-osx-x64.tgz"
    )
    response.raise_for_status()
    sha = hashlib.sha256(response.content).hexdigest()
    assert sha == "0c604fb5776371e59f4c641de54ea65f24917b8e539a577484a94d2f66f6e31d"
    tarfile.TarFile.gzopen(None, fileobj=io.BytesIO(response.content)).extractall("lib")
else:
    raise RuntimeError("use e.g. apt-get")
