# Based on a file that pynsis generated. Used only on windows.
import os
import site
import sys

from porcupine.__main__ import main

pkgdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pkgs")
sys.path.insert(0, pkgdir)
site.addsitedir(pkgdir)  # Ensure .pth files in pkgdir are handled properly
os.environ["PYTHONPATH"] = pkgdir + os.pathsep + os.environ.get("PYTHONPATH", "")
main()
