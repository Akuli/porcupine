# "Temporary" hack to debug #379
import os
import sys
import threading

if sys.version_info >= (3, 9):
    sys.exit(0)

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

old = """
    tlock = _main_thread._tstate_lock
"""
new = """
    if "pytest" in __import__("sys").modules:
        for x in enumerate():
            print("JOINING:", x, x._target, x.run, flush=True)
    tlock = _main_thread._tstate_lock
"""

print(threading.__file__, "--> threading.py")
content = open(threading.__file__).read()
assert content.count(old) == 1, content.count(old)
open("threading.py", "w").write(content.replace(old, new))
