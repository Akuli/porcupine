"""Run commands within the Porcupine window."""
from __future__ import annotations

import logging
import queue
import re
import subprocess
import threading
import tkinter
from pathlib import Path
from typing import Iterator

from porcupine import get_tab_manager, images, utils

log = logging.getLogger(__name__)


filename_regex_parts = [
    # c compiler output
    # playground.c:4:9: warning: ...
    r'^([^:]+):([0-9]+)(?=:)'
]
filename_regex = '|'.join(r'(?:' + part + r')' for part in filename_regex_parts)


def parse_paths(cwd: Path, text: str) -> Iterator[tuple[str, Path, int] | str]:
    previous_end = 0
    for match in re.finditer(filename_regex, text):
        filename, lineno = (value for value in match.groups() if value is not None)
        path = cwd / filename  # doesn't use cwd if filename is absolute
        if not path.is_file():
            continue

        yield text[previous_end:match.start()]
        yield (match.group(0), path, int(lineno))
        previous_end = match.end()

    yield text[previous_end:]


class NoTerminalRunner:
    def __init__(self, master: tkinter.Misc) -> None:
        # TODO: better coloring that follows the pygments theme
        self.textwidget = tkinter.Text(master, height=12, state="disabled")
        self.textwidget.tag_config("info", foreground="blue")
        self.textwidget.tag_config("output")  # use default colors
        self.textwidget.tag_config("error", foreground="red")
        self.textwidget.tag_config("link", underline=True)
        self.textwidget.tag_bind("link", "<Enter>", self._enter_link)
        self.textwidget.tag_bind("link", "<Leave>", self._leave_link)
        self.textwidget.tag_bind("link", "<Button-1>", self._open_link)

        self._output_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._running_process: subprocess.Popen[bytes] | None = None
        self._queue_handler()

        self._links: dict[str, tuple[str, int]] = {}
        self._cwd: Path | None = None

    # TODO: much links code copy/pasted from aboutdialog plugin
    def _enter_link(self, junk_event: tkinter.Event[tkinter.Misc]) -> None:
        self.textwidget.config(cursor="hand2")

    def _leave_link(self, junk_event: tkinter.Event[tkinter.Misc]) -> None:
        self.textwidget.config(cursor="")

    def _open_link(self, junk_event: tkinter.Event[tkinter.Misc]) -> None:
        for tag in self.textwidget.tag_names("current"):
            if tag.startswith("link-"):
                path, lineno = self._links[tag]
                tab = get_tab_manager().open_file(path)
                tab.textwidget.mark_set("insert", f"{lineno}.0")
                tab.textwidget.see("insert")
                tab.textwidget.tag_remove("sel", "1.0", "end")
                tab.textwidget.tag_add("sel", "insert", "insert lineend")
                break

    def run_command(self, cwd: Path, command: str) -> None:
        self._cwd = cwd

        # this is a daemon thread because i don't care what the fuck
        # happens to it when python exits
        threading.Thread(target=self._runner_thread, args=[cwd, command], daemon=True).start()

    def _runner_thread(self, cwd: Path, command: str) -> None:
        process: subprocess.Popen[bytes] | None = None

        def emit_message(msg: tuple[str, str]) -> None:
            if process is not None and self._running_process is not process:
                # another _run_command() is already running
                return
            self._output_queue.put(msg)

        emit_message(("clear", ""))
        emit_message(("info", command + "\n"))

        try:
            process = self._running_process = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                **utils.subprocess_kwargs,
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
        else:
            emit_message(("error", f"The process failed with status {process.returncode}."))

    def _queue_handler(self) -> None:
        messages: list[tuple[str, str]] = []
        while True:
            try:
                messages.append(self._output_queue.get(block=False))
            except queue.Empty:
                break

        if messages:
            self.textwidget.config(state="normal")
            for tag, text in messages:
                if tag == "clear":
                    assert not text
                    self.textwidget.delete("1.0", "end")
                    for tag in self._links.keys():
                        self.textwidget.tag_delete(tag)
                    self._links.clear()
                else:
                    assert self._cwd is not None
                    for part in parse_paths(self._cwd, text):
                        if isinstance(part, str):
                            self.textwidget.insert("end", part, [tag])
                        else:
                            text, path, lineno = part
                            link_specific_tag = f"link-{len(self._links)}"
                            self._links[link_specific_tag] = (path, lineno)
                            self.textwidget.insert("end", text, [tag, "link", link_specific_tag])
            self.textwidget.config(state="disabled")

        self.textwidget.after(100, self._queue_handler)

    def destroy(self, junk: object = None) -> None:
        self.textwidget.destroy()

        # Saving self._running_process to local var avoids race condition and
        # makes mypy happy.
        process = self._running_process
        if process is not None:
            process.kill()


# keys are tkinter widget paths from str(tab), they identify tabs uniquely
_no_terminal_runners: dict[str, NoTerminalRunner] = {}


# succeeded_callback() will be ran from tkinter if the command returns 0
def run_command(command: str, cwd: Path) -> None:

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
    runner.run_command(cwd, command)
