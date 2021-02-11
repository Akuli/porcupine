import logging
import os
import platform
import subprocess
import sys
import threading
import time
import types
from datetime import datetime

from porcupine import _logs


# should be possible to start many porcupines at almost exactly the same time
def test_race_conditions():
    timed_out = [False] * 10

    def thread_target(index):
        try:
            subprocess.run([sys.executable, '-m', 'porcupine'], timeout=2, stdout=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            timed_out[index] = True

    threads = [
        threading.Thread(name=f'race-thread-{i}', target=thread_target, args=[i])
        for i in range(len(timed_out))
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert timed_out == [True] * len(timed_out)


def test_remove_old_logs(monkeypatch, caplog):
    long_time_ago = datetime(year=1987, month=6, day=5, hour=4, minute=3, second=2)

    with monkeypatch.context() as monkey:
        monkey.setattr(_logs, 'datetime', types.SimpleNamespace(now=(lambda: long_time_ago)))

        _logs._open_log_file().close()
        _logs._open_log_file().close()
        _logs._open_log_file().close()
        _logs._open_log_file().close()

    caplog.set_level(logging.INFO)
    _logs._remove_old_logs()

    text = caplog.text
    assert f'logs{os.sep}1987-06-05T04-03-02.txt is more than 7 days old, removing' in text
    assert f'logs{os.sep}1987-06-05T04-03-02_1.txt is more than 7 days old, removing' in text
    assert f'logs{os.sep}1987-06-05T04-03-02_2.txt is more than 7 days old, removing' in text
    assert f'logs{os.sep}1987-06-05T04-03-02_3.txt is more than 7 days old, removing' in text


def test_log_path_printed():
    # -u for unbuffered, helps get printed output when python is killed
    process = subprocess.Popen([sys.executable, '-u', '-m', 'porcupine'], stdout=subprocess.PIPE)
    try:
        time.sleep(1)
    finally:
        process.kill()

    line = process.stdout.readline()
    if sys.platform == 'win32':
        assert line.startswith(b'log file: ')
    else:
        assert line.startswith(b'log file: /')  # absolute path
    assert line.endswith((b'.txt\n', b'.txt\r\n'))
