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
    # c compiler output, also many other tools
    # TODO: support spaces in file names?
    # playground.c:4:9: warning: ...
    r"([^\n\s:]+):([0-9]+)(?=:)",
    # python error
    r'File "([^\n"]+)", line ([0-9]+)',
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
        self.started = False

    def run(self, command: str) -> None:
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"  # same as passing -u option to python (#802)

        # Update needed to get width and height, but causes key bindings to execute
        self._textwidget.update()
        width, height = textutils.textwidget_size(self._textwidget)

        font = tkinter.font.Font(name="TkFixedFont", exists=True)
        env["COLUMNS"] = str(width // font.measure("a"))
        env["LINES"] = str(height // font.metrics("linespace"))

        threading.Thread(target=self._thread_target, args=[command, env], daemon=True).start()
        self._queue_handler()
        self.started = True

    def _thread_target(self, command: str, env: dict[str, str]) -> None:
        self._queue.put(("info", command + "\n"))

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
        while True:
            bytez = self._shell_process.stdout.read1()  # type: ignore
            if not bytez:
                break
            text = bytez.decode(locale.getpreferredencoding(), errors="replace")
            self._queue.put(("output", utils.tkinter_safe_string(text).replace(os.linesep, "\n")))

        status = self._shell_process.wait()
        if status == 0:
            self._queue.put(("info", "The process completed successfully."))
        else:
            self._queue.put(("error", f"The process failed with status {status}."))
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
            for tag, text in messages:
                if tag == "end":
                    assert not text
                    get_tab_manager().event_generate("<<FileSystemChanged>>")
                else:
                    self._textwidget.insert("end", text, [tag])
                    # Add links to full lines
                    linked_line_count = text.count("\n")
                    self._link_manager.add_links(
                        start=f"end - 1 char linestart - {linked_line_count} lines",
                        end="end - 1 char linestart",
                    )

            self._textwidget.config(state="disabled")

        self._timeout_id = self._textwidget.after(100, self._queue_handler)

    def stop(self, *, quitting: bool = False) -> None:
        if self._timeout_id is not None:
            self._textwidget.after_cancel(self._timeout_id)
            self._timeout_id = None

        if self._shell_process is None:
            return

        try:
            # On non-windows we can stop the shell so that it can't spawn more children
            # On windows there is a race condition
            if sys.platform != "win32":
                self._shell_process.send_signal(signal.SIGSTOP)

            # If we kill the shell, its child processes will keep running.
            # But they will reparent to pid 1 so can no longer list them
            children = psutil.Process(self._shell_process.pid).children()
            if self._shell_process.poll() is None:
                # shell still alive, the pid wasn't reused
                self._shell_process.kill()
                for child in children:
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        # Child already dead, but we need to kill other children
                        pass

        # shell can die at any time
        # non-psutil errors happen in langserver plugin, not sure if needed here
        except (psutil.NoSuchProcess, ProcessLookupError):
            pass

        if not quitting:
            get_tab_manager().event_generate("<<FileSystemChanged>>")


class NoTerminalRunner:
    def __init__(self, master: tkinter.Misc) -> None:
        # TODO: better coloring that follows the pygments theme
        self.textwidget = create_passive_text_widget(
            master, font="TkFixedFont", is_focusable=True, name="run_output", wrap="char"
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
            # This prevents a bug where smashing F5 runs in parallel
            if not self.executor.started:
                return

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
