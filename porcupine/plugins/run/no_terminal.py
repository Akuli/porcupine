"""Run commands within the Porcupine window."""
from __future__ import annotations

import atexit
import locale
import logging
import os
import queue
import re
import subprocess
import threading
import tkinter
from functools import partial
from pathlib import Path
from typing import Callable

import psutil

from porcupine import get_tab_manager, get_vertical_panedwindow, images, settings, textutils, utils
from porcupine.textutils import create_passive_text_widget

log = logging.getLogger(__name__)


filename_regex_parts = [
    # c compiler output
    # playground.c:4:9: warning: ...
    r"\b([^:]+):([0-9]+)(?=:)",
    # python error
    r'File "([^"]+)", line ([0-9]+)',
]
filename_regex = "|".join(r"(?:" + part + r")" for part in filename_regex_parts)


def open_file_with_line_number(path: Path, lineno: int) -> None:
    tab = get_tab_manager().open_file(path)
    if tab is not None:
        tab.textwidget.mark_set("insert", f"{lineno}.0")
        tab.textwidget.see("insert")
        tab.textwidget.tag_remove("sel", "1.0", "end")
        tab.textwidget.tag_add("sel", "insert", "insert lineend")


class NoTerminalRunner:
    def __init__(self, master: tkinter.Misc) -> None:
        # TODO: better coloring that follows the pygments theme
        self.textwidget = create_passive_text_widget(
            master, font="TkFixedFont", is_focusable=True, name="run_output"
        )
        self.textwidget.tag_config("info", foreground="blue")
        self.textwidget.tag_config("output")  # use default colors
        self.textwidget.tag_config("error", foreground="red")

        self._cwd: Path | None = None  # can't pass data to callbacks when adding link
        self._link_manager = textutils.LinkManager(
            self.textwidget, filename_regex, self._get_link_opener
        )
        self.textwidget.tag_config("link", underline=True)

        self._output_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._running_process: subprocess.Popen[bytes] | None = None
        self.run_id = 0
        self._queue_handler()

    def _get_link_opener(self, match: re.Match[str]) -> Callable[[], None] | None:
        assert self._cwd is not None

        filename, lineno = (value for value in match.groups() if value is not None)
        path = self._cwd / filename  # doesn't use cwd if filename is absolute
        if not path.is_file():
            return None
        return partial(open_file_with_line_number, path, int(lineno))

    def run_command(self, cwd: Path, command: str) -> None:
        self._cwd = cwd

        # this is a daemon thread because i don't care what the fuck
        # happens to it when python exits
        threading.Thread(
            target=self._runner_thread, args=[cwd, command, self.run_id], daemon=True
        ).start()

    def _runner_thread(self, cwd: Path, command: str, run_id: int) -> None:
        process: subprocess.Popen[bytes] | None = None

        def emit_message(msg: tuple[str, str]) -> None:
            if self.run_id == run_id:
                self._output_queue.put(msg)

        emit_message(("info", command + "\n"))

        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"  # same as passing -u option to python (#802)

        try:
            process = self._running_process = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                env=env,
                **utils.subprocess_kwargs,
            )
        except OSError as e:
            emit_message(("error", f"{type(e).__name__}: {e}\n"))
            log.debug("here's full traceback", exc_info=True)
            return

        assert process.stdout is not None
        for bytez in process.stdout:
            line = bytez.decode(locale.getpreferredencoding(), errors="replace")
            emit_message(("output", utils.tkinter_safe_string(line).replace(os.linesep, "\n")))
        process.communicate()  # make sure process.returncode is set

        if process.returncode == 0:
            # can't do succeeded_callback() here because this is running
            # in a thread and succeeded_callback() does tkinter stuff
            emit_message(("info", "The process completed successfully."))
        else:
            emit_message(("error", f"The process failed with status {process.returncode}."))
        emit_message(("end", ""))

    def _queue_handler(self) -> None:
        messages: list[tuple[str, str]] = []
        while True:
            try:
                messages.append(self._output_queue.get(block=False))
            except queue.Empty:
                break

        if messages:
            self.textwidget.config(state="normal")
            for tag, output_line in messages:
                if tag == "end":
                    assert not output_line
                    get_tab_manager().event_generate("<<FileSystemChanged>>")
                else:
                    self._link_manager.append_text(output_line, [tag])
            self.textwidget.config(state="disabled")

        self.textwidget.after(100, self._queue_handler)

    def clear(self) -> None:
        self.textwidget.config(state="normal")
        self.textwidget.delete("1.0", "end")
        self.textwidget.config(state="disabled")
        self._link_manager.delete_all_links()  # prevent memory leak

    # This method has a couple race conditions but works well enough in practice
    def kill_process(self) -> None:
        if self._running_process is None:
            return
        shell = self._running_process
        self._running_process = None

        try:
            # is the shell alive?
            shell.wait(timeout=0)
        except subprocess.TimeoutExpired:
            # yes, it is alive
            #
            # If we kill the shell, its child processes will keep running,
            # but they will reparent to pid 1 so we can no longer get a
            # list of them.
            try:
                children = psutil.Process(shell.pid).children()
            except psutil.NoSuchProcess:
                # Would run if shell dies after asking if it's alive.
                # Don't know if this ever runs in practice, but there's
                # similar code in langserver plugin and it runs sometimes.
                return
            shell.kill()  # Do not create more children
            for child in children:
                child.kill()
            self._running_process = None


runner: NoTerminalRunner | None = None


@atexit.register
def _kill_process_when_quitting_porcupine():
    if runner is not None:
        runner.kill_process()


# succeeded_callback() will be ran from tkinter if the command returns 0
def run_command(command: str, cwd: Path) -> None:
    global runner
    log.info(f"Running {command} in {cwd}")
    if runner is None:
        runner = NoTerminalRunner(get_vertical_panedwindow())
        get_vertical_panedwindow().add(runner.textwidget, after=get_tab_manager(), stretch="never")
        settings.remember_pane_size(
            get_vertical_panedwindow(), runner.textwidget, "run_command_output_height", 200
        )

        def on_close(event: tkinter.Event[tkinter.Misc]) -> None:
            global runner
            assert runner is not None
            runner.textwidget.destroy()
            runner.kill_process()
            runner = None

        closebutton = tkinter.Label(
            runner.textwidget, image=images.get("closebutton"), cursor="hand2"
        )
        closebutton.bind("<Button-1>", on_close, add=True)
        closebutton.place(relx=1, rely=0, anchor="ne")

    runner.run_id += 1
    runner.kill_process()
    runner.clear()
    runner.run_command(cwd, command)
