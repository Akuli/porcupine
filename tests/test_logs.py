import logging
import os
import subprocess
import sys
import threading
from datetime import datetime

import pytest

from porcupine import _logs


# should be possible to start many porcupines at almost exactly the same time
def test_race_conditions():
    timed_out = [False] * 10

    def thread_target(index):
        try:
            subprocess.run(
                [sys.executable, "-m", "porcupine"], timeout=2, stdout=subprocess.DEVNULL
            )
        except subprocess.TimeoutExpired:
            timed_out[index] = True

    threads = [
        threading.Thread(name=f"race-thread-{i}", target=thread_target, args=[i])
        for i in range(len(timed_out))
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert timed_out == [True] * len(timed_out)


def test_remove_old_logs(monkeypatch, caplog, mocker):
    long_time_ago = datetime(year=1987, month=6, day=5, hour=4, minute=3, second=2)

    with monkeypatch.context() as monkey:
        mock = mocker.Mock()
        mock.now.return_value = long_time_ago
        monkey.setattr("porcupine._logs.datetime", mock)

        _logs._open_log_file().close()
        _logs._open_log_file().close()
        _logs._open_log_file().close()
        _logs._open_log_file().close()

    caplog.set_level(logging.INFO)
    _logs._remove_old_logs()

    text = caplog.text
    assert f"logs{os.sep}1987-06-05T04-03-02.txt is more than 7 days old, removing" in text
    assert f"logs{os.sep}1987-06-05T04-03-02_1.txt is more than 7 days old, removing" in text
    assert f"logs{os.sep}1987-06-05T04-03-02_2.txt is more than 7 days old, removing" in text
    assert f"logs{os.sep}1987-06-05T04-03-02_3.txt is more than 7 days old, removing" in text


def test_log_path_printed(mocker):
    mock = mocker.patch("porcupine._logs.print")
    mock.side_effect = ZeroDivisionError  # to make it stop when it prints
    with pytest.raises(ZeroDivisionError):
        _logs.setup()

    mock.assert_called_once()
    [printed] = mock.call_args[0]
    assert printed.startswith("log file: ")
    assert os.path.isfile(printed[len("log file: ") :])
