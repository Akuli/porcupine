import itertools
import logging
import os
import platform

if platform.system() == 'Windows':  # noqa
    import msvcrt
else:   # noqa
    import fcntl

from porcupine import dirs


def _lock(fileno):
    """Try to lock a file. Return True on success."""
    # closing the file unlocks it, so we don't need to unlock here
    if platform.system() == 'Windows':
        try:
            msvcrt.locking(fileno, msvcrt.LK_NBLCK, 10)
            return True
        except PermissionError:
            return False
    else:
        try:
            fcntl.lockf(fileno, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        # the docs recommend catching both of these
        except (BlockingIOError, PermissionError):
            return False


def _open_log_file():
    """Open a Porcupine log file.

    Usually this opens and overwrites log.txt. If another Porcupine
    process has it currently opened, this opens log1.txt instead, then
    log2.txt and so on.
    """
    # create an iterator 'log.txt', 'log2.txt', 'log3.txt', ...
    filenames = itertools.chain(
        ['log.txt'],
        map('log{}.txt'.format, itertools.count(start=2)),
    )

    for filename in filenames:
        path = os.path.join(dirs.cachedir, filename)
        # unfortunately there's not a mode that would open in write but
        # not truncate like 'w' or seek to end like 'a'
        fileno = os.open(path, os.O_WRONLY | os.O_CREAT, 0o644)

        if _lock(fileno):
            # now we can delete the old content, can't use os.truncate
            # here because it doesn't exist on windows
            file = open(fileno, 'w')
            file.truncate(0)
            return file
        else:
            os.close(fileno)


# FileHandler doesn't take already opened files and StreamHandler
# doesn't close the file :(
class _ClosingStreamHandler(logging.StreamHandler):

    def close(self):
        self.stream.close()


def setup(verbose):
    printformat = logging.Formatter("%(name)s: %(message)s")
    fileformat = logging.Formatter(
        "[PID {} %(levelname)s] %(name)s: %(message)s"
        .format(os.getpid()))

    printhandler = logging.StreamHandler()
    printhandler.setLevel(logging.DEBUG if verbose else logging.ERROR)
    printhandler.setFormatter(fileformat if verbose else printformat)

    filehandler = _ClosingStreamHandler(_open_log_file())
    filehandler.setLevel(logging.DEBUG)
    filehandler.setFormatter(fileformat)

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[printhandler, filehandler],
    )
