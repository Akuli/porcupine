"""Run commands within the Porcupine window."""
from __future__ import annotations

import locale
import logging
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import tkinter
from functools import partial
from pathlib import Path
from tkinter import ttk
from typing import Callable

import psutil

from porcupine import (
    get_tab_manager,
    get_vertical_panedwindow,
    images,
    menubar,
    settings,
    textutils,
    utils,
)
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


class Executor:

    def __init__(self, cwd: Path, textwidget: tkinter.Text, link_manager: textutils.LinkManager):
        self.cwd = cwd
        self._textwidget = textwidget
        self._link_manager = link_manager

        self._shell_process: subprocess.Popen[bytes] | None = None
        self._queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._timeout_id: str | None = None

    def run(self, command: str, )->None:
        threading.Thread(target=self._thread_target, args=[command], daemon=True).start()
        self._queue_handler()

    def _thread_target(self, command: str) -> None:
        self._queue.put(("info", command + "\n"))

        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"  # same as passing -u option to python (#802)
        try:
            self._shell_process = subprocess.Popen(
                command,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                env=env,
                **utils.subprocess_kwargs,
            )
        except OSError as e:
            self._queue.put(("error", f"{type(e).__name__}: {e}\n"))
            log.debug("here's full traceback", exc_info=True)
            return

        assert self._shell_process.stdout is not None
        for bytez in self._shell_process.stdout:
            line = bytez.decode(locale.getpreferredencoding(), errors="replace")
            self._queue.put(("output", utils.tkinter_safe_string(line).replace(os.linesep, "\n")))
        self._shell_process.communicate()  # make sure self._shell_process.returncode is set

        if self._shell_process.returncode == 0:
            # can't do succeeded_callback() here because this is running
            # in a thread and succeeded_callback() does tkinter stuff
            self._queue.put(("info", "The process completed successfully."))
        else:
            self._queue.put(("error", f"The process failed with status {self._shell_process.returncode}."))
        self._queue.put(("end", ""))

    def _queue_handler(self) -> None:
        messages: list[tuple[str, str]] = []
        while True:
            try:
                messages.append(self._queue.get(block=False))
            except queue.Empty:
                break

        if messages:
            self._textwidget.config(state="normal")
            for tag, output_line in messages:
                if tag == "end":
                    assert not output_line
                    get_tab_manager().event_generate("<<FileSystemChanged>>")
                else:
                    self._link_manager.append_text(output_line, [tag])
            self._textwidget.config(state="disabled")

        self._timeout_id = self._textwidget.after(100, self._queue_handler)

    def stop(self, *, quitting: bool = False) -> None:
        if self._timeout_id is not None:
            self._textwidget.after_cancel(self._timeout_id)
            self._timeout_id = None

        if self._shell_process is None:
            return

        if self._shell_process.poll() is None:  # if shell still alive
            # On non-windows we can stop the shell so that it can't spawn more children
            # On windows there is a race condition
            if sys.platform != "win32":
                self._shell_process.send_signal(signal.SIGSTOP)

            # If we kill the shell, its child processes will keep running,
            # but they will reparent to pid 1 so we can no longer get a
            # list of them.
            try:
                children = psutil.Process(self._shell_process.pid).children()
            except psutil.NoSuchProcess:
                # Would run if shell dies after asking if it's alive.
                # Don't know if this ever runs in practice, but there's
                # similar code in langserver plugin and it runs sometimes.
                return
            self._shell_process.kill()  # Do not create more children
            for child in children:
                try:
                    child.kill()
                except psutil.NoSuchProcess:  # child already died
                    pass

        if not quitting:
            get_tab_manager().event_generate("<<FileSystemChanged>>")


class NoTerminalRunner:
    def __init__(self, master: tkinter.Misc) -> None:
        # TODO: better coloring that follows the pygments theme
        self.textwidget = create_passive_text_widget(
            master, font="TkFixedFont", is_focusable=True, name="run_output"
        )
        self.textwidget.tag_config("info", foreground="blue")
        self.textwidget.tag_config("output")  # use default colors
        self.textwidget.tag_config("error", foreground="red")
        self.textwidget.bind("<Destroy>", self._stop_executor, add=True)

        self._link_manager = textutils.LinkManager(
            self.textwidget, filename_regex, self._get_link_opener
        )
        self.textwidget.tag_config("link", underline=True)
        self.executor: Executor | None = None

    def _stop_executor(self, junk_event: object) -> None:
        if self.executor is not None:
            self.executor.stop(quitting=True)

    def _get_link_opener(self, match: re.Match[str]) -> Callable[[], None] | None:
        assert self.executor is not None

        filename, lineno = (value for value in match.groups() if value is not None)
        path = self.executor.cwd / filename  # doesn't use cwd if filename is absolute
        if not path.is_file():
            return None
        return partial(open_file_with_line_number, path, int(lineno))

    def run_command(self, cwd: Path, command: str) -> None:
        if self.executor is not None:
            self.executor.stop()

        self.textwidget.config(state="normal")
        self.textwidget.delete("1.0", "end")
        self.textwidget.config(state="disabled")
        self._link_manager.delete_all_links()  # prevent memory leak

        self.executor = Executor(cwd, self.textwidget, self._link_manager)
        self.executor.run(command)


runner: NoTerminalRunner | None = None


def setup() -> None:
    global runner
    assert runner is None
    runner = NoTerminalRunner(get_vertical_panedwindow())
    get_vertical_panedwindow().add(
        runner.textwidget, after=get_tab_manager(), stretch="never", hide=True
    )
    settings.remember_pane_size(
        get_vertical_panedwindow(), runner.textwidget, "run_command_output_height", 200
    )

    def toggle_visible(junk_event: object = None) -> None:
        assert runner is not None
        is_hidden = get_vertical_panedwindow().panecget(runner.textwidget, "hide")
        get_vertical_panedwindow().paneconfigure(runner.textwidget, hide=not is_hidden)

    closebutton = ttk.Label(runner.textwidget, image=images.get("closebutton"), cursor="hand2")
    closebutton.place(relx=1, rely=0, anchor="ne")
    closebutton.bind("<Button-1>", toggle_visible, add=True)

    menubar.get_menu("Run").add_command(label="Show/hide output", command=toggle_visible)


# succeeded_callback() will be ran from tkinter if the command returns 0
def run_command(command: str, cwd: Path) -> None:
    log.info(f"Running {command} in {cwd}")
    assert runner is not None
    get_vertical_panedwindow().paneconfigure(runner.textwidget, hide=False)
    runner.run_command(cwd, command)
