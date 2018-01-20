import logging
import os
import sys


def setup():
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(
        "[PID {} %(levelname)s] %(name)s: %(message)s".format(os.getpid())
    ))
    logging.basicConfig(level=logging.DEBUG, handlers=[handler])
