# Temporary hax file that runs last
import pprint
import threading


def test_zzz():
    for thread in threading.enumerate():
        pprint.pprint(vars(thread))
