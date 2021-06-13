"""Run commands within the Porcupine window."""
from __future__ import annotations

import logging
import pathlib
import queue
import subprocess
import threading
import tkinter
from typing import Callable, Dict, List, Tuple, Union

from porcupine import get_tab_manager, images, utils

log = logging.getLogger(__name__)

QueueMessage = Tuple[str, Union[str, Callable[[], None]]]


class NoTerminalRunner:
    def __init__(self, master: tkinter.Misc) -> None:
        # TODO: better coloring that follows the pygments theme
        self.textwidget = tkinter.Text(master, height=12, state="disabled")
        self.textwidget.tag_config("info", foreground="blue")
        self.textwidget.tag_config("output")  # use default colors
        self.textwidget.tag_config("error", foreground="red")

        self._output_queue: queue.Queue[QueueMessage] = queue.Queue()
        self._running_process: subprocess.Popen[bytes] | None = None
        self._queue_clearer()

    def _runner_thread(
        self, workingdir: pathlib.Path, command: List[str], succeeded_callback: Callable[[], None]
    ) -> None:
        process: subprocess.Popen[bytes] | None = None

        def emit_message(msg: QueueMessage) -> None:
            if process is not None and self._running_process is not process:
                # another _run_command() is already running
                return
            self._output_queue.put(msg)

        emit_message(("clear", ""))
        emit_message(("info", " ".join(map(utils.quote, command)) + "\n"))

        try:
            process = self._running_process = subprocess.Popen(
                command, cwd=workingdir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
        except OSError as e:
            emit_message(("error", f"{type(e).__name__}: {e}\n"))
            log.debug("here's full traceback", exc_info=True)
            return

        assert process.stdout is not None
        for line in process.stdout:
            # TODO: is utf-8 the correct choice on all platforms?
            emit_message(("output", line.decode("utf-8", errors="replace")))
        process.communicate()  # make sure process.returncode is set

        if process.returncode == 0:
            # can't do succeeded_callback() here because this is running
            # in a thread and succeeded_callback() does tkinter stuff
            emit_message(("info", "The process completed successfully."))
            emit_message(("run", succeeded_callback))
        else:
            emit_message(("error", f"The process failed with status {process.returncode}."))

    def run_command(
        self, workingdir: pathlib.Path, command: List[str], succeeded_callback: Callable[[], None]
    ) -> None:
        # this is a daemon thread because i don't care what the fuck
        # happens to it when python exits
        threading.Thread(
            target=self._runner_thread, args=[workingdir, command, succeeded_callback], daemon=True
        ).start()

    def _queue_clearer(self) -> None:
        messages: List[QueueMessage] = []
        while True:
            try:
                messages.append(self._output_queue.get(block=False))
            except queue.Empty:
                break

        if messages:
            self.textwidget.config(state="normal")
            for msg in messages:
                if msg[0] == "clear":
                    assert not msg[1]
                    self.textwidget.delete("1.0", "end")
                elif msg[0] == "run":
                    assert not isinstance(msg[1], str)
                    msg[1]()
                else:
                    tag, text = msg
                    assert isinstance(text, str)
                    self.textwidget.insert("end", text, tag)
            self.textwidget.config(state="disabled")

        self.textwidget.after(100, self._queue_clearer)

    def destroy(self, junk: object = None) -> None:
        self.textwidget.destroy()

        # Saving self._running_process to local var avoids race condition and
        # makes mypy happy.
        process = self._running_process
        if process is not None:
            process.kill()


# keys are tkinter widget paths from str(tab), they identify tabs uniquely
_no_terminal_runners: Dict[str, NoTerminalRunner] = {}


# succeeded_callback() will be ran from tkinter if the command returns 0
def run_command(
    workingdir: pathlib.Path,
    command: List[str],
    succeeded_callback: Callable[[], None] = (lambda: None),
) -> None:

    tab = get_tab_manager().select()
    assert tab is not None

    try:
        runner = _no_terminal_runners[str(tab)]
    except KeyError:
        runner = NoTerminalRunner(tab.bottom_frame)
        _no_terminal_runners[str(tab)] = runner

        # TODO: can this also be ran when tab is closed?
        def on_close(event: tkinter.Event[tkinter.Misc]) -> None:
            runner.destroy()
            del _no_terminal_runners[str(tab)]

        closebutton = tkinter.Label(
            runner.textwidget, image=images.get("closebutton"), cursor="hand2"
        )
        closebutton.bind("<Button-1>", on_close, add=True)
        closebutton.place(relx=1, rely=0, anchor="ne")

    runner.textwidget.pack(side="top", fill="x")
    runner.run_command(workingdir, command, succeeded_callback)
