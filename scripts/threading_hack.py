# "Temporary" hack to debug #379
import os
import sys
import threading
from pathlib import Path

if sys.version_info >= (3, 8):
    sys.exit(0)

os.chdir(Path(__file__).absolute().parent.parent)

old = """
    while t:
        t.join()
"""
new = """
    while t:
        print("JOINING:", t, t._target, t.run)
        t.join()
"""

print(threading.__file__, "--> threading.py")
content = Path(threading.__file__).read_text()
assert content.count(old) == 1, content.count(old)
Path("threading.py").write_text(content.replace(old, new))
