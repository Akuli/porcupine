"""Run commands within the Porcupine window."""
from __future__ import annotations

import locale
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
from porcupine.textutils import track_changes, add_change_blocker

import psutil


filename_regex_parts = [
    # c compiler output, also many other tools
    # TODO: support spaces in file names?
    # playground.c:4:9: warning: ...
    r"([^\n\s:()]+):([0-9]+)",
    # python error
    r'File "([^\n"]+)", line ([0-9]+)',
    # valgrind, SDL_assert() etc
    # blah blah: some_function (filename.c:123)
    r"\(([^\n():]+):([0-9]+)\)",
]
filename_regex = "|".join(r"(?:" + part + r")" for part in filename_regex_parts)


MAX_SCROLLBACK = 5000
OUTPUT_TAGS = {"info": "Token.Keyword", "output": "Token.Text", "error": "Token.Name.Exception"}


class Executor:
    def __init__(self, cwd: Path, textwidget: tkinter.Text):
        self.cwd = cwd
        self._textwidget = textwidget

        self._shell_process: subprocess.Popen[bytes] | None = None
        self._input_queue: queue.Queue[bytes] = queue.Queue(maxsize=1)
        self._queue: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=1)
        self._timeout_id: str | None = None
        self.started = False
        self.paused = False
        self._thread: threading.Thread | None = None

    def run(self, command: str) -> None:
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"  # same as passing -u option to python (#802)

        self._thread = threading.Thread(
            target=self._thread_target, args=[command, env], daemon=True
        )
        self._thread.start()
        self._poll_queue_and_put_to_textwidget()
        self.started = True

    @property
    def running(self) -> bool:
        return self._shell_process is not None and self._shell_process.poll() is None

    def _thread_target(self, command: str, env: dict[str, str]) -> None:
        self._queue.put(("info", command + "\n"))

        popen_kwargs = {}

        try:
            self._shell_process = subprocess.Popen(
                command,
                cwd=self.cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                env=env,
                **popen_kwargs,
            )
        except OSError as e:
            self._queue.put(("error", f"{type(e).__name__}: {e}\n"))
            return

        assert self._shell_process.stdout is not None
        while True:
            bytez = self._shell_process.stdout.read1()  # type: ignore
            if not bytez:
                break
            text = bytez.decode(locale.getpreferredencoding(), errors="replace")
            self._queue.put(("output", text.replace("\r\n", "\n")))

        status = self._shell_process.wait()
        if status == 0:
            self._queue.put(("info", "The process completed successfully."))
        else:
            self._queue.put(("error", f"The process failed with status {status}."))
        self._queue.put(("end", ""))

    def _handle_queued_item(self, message_type: str, text: str) -> None:
        if message_type == "end":
            assert not text
        else:
            scrolled_to_end = self._textwidget.yview()[1] == 1.0

            self._textwidget.insert("end", text, [OUTPUT_TAGS[message_type], "output"])
            if scrolled_to_end:
                self._textwidget.yview_moveto(1)

        self._textwidget.delete("1.0", f"end - {MAX_SCROLLBACK} lines")

    def _poll_queue_and_put_to_textwidget(self) -> None:
        # too many iterations here freezes the GUI when an infinite loop with print is running
        for iteration in range(10):
            try:
                message_type, text = self._queue.get(block=False)
            except queue.Empty:
                break
            self._handle_queued_item(message_type, text)

        self._timeout_id = self._textwidget.after(50, self._poll_queue_and_put_to_textwidget)

    def send_signal(self, signal: signal.Signals) -> None:
        if self._shell_process is None:
            return

        try:
            process = psutil.Process(self._shell_process.pid)
            process.send_signal(signal)
            for child in process.children():
                try:
                    child.send_signal(signal)
                except psutil.NoSuchProcess:
                    pass

        except (psutil.NoSuchProcess, ProcessLookupError):
            pass

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

        else:
            if not quitting:
                assert self._thread is not None
                assert self._thread.is_alive()

                if sys.platform == "win32":
                    kill_status = 1
                else:
                    kill_status = -signal.SIGKILL

                # Consume queue until the thread stops
                while True:
                    message_type, text = self._queue.get(block=True)
                    # For killing messages, a separate "Killed." will be added below
                    if (message_type, text) != (
                        "error",
                        f"The process failed with status {kill_status}.",
                    ):
                        self._handle_queued_item(message_type, text)
                    if message_type == "end":
                        break
                self._thread.join()

                self._handle_queued_item("error", "Killed.")

    def write_to_stdin(self, data: bytes):
        if self._shell_process is not None:
            self._shell_process.stdin.write(data)
            self._shell_process.stdin.flush()  # TODO: may block, maybe that isn't an issue in practice?

    def close_stdin(self):
        if self._shell_process is not None:
            self._shell_process.stdin.close()


class TerribleTerminalEmulator(tkinter.Text):
    def __init__(self, master: tkinter.Misc) -> None:
        super().__init__(master, blockcursor=True, insertunfocussed='hollow')
        self.bind("<BackSpace>", self._handle_backspace)

        track_changes(self)
        add_change_blocker(self, self._editing_should_be_blocked)
        self._in_a_python_method = False

    # Keep _in_a_python_method up to date
    def insert(self, *args, **kwargs):
        self._in_a_python_method = True
        try:
            return super().insert(*args, **kwargs)
        finally:
            self._in_a_python_method = False

    def delete(self, *args, **kwargs):
        self._in_a_python_method = True
        try:
            return super().delete(*args, **kwargs)
        finally:
            self._in_a_python_method = False

    def replace(self, *args, **kwargs):
        self._in_a_python_method = True
        try:
            return super().replace(*args, **kwargs)
        finally:
            self._in_a_python_method = False

    def _editing_should_be_blocked(self) -> bool:
        # Do not block if we are currently in a python method e.g. insert()
        # This blocking is only for Tk's default key bindings (implemented in Tcl).
        if self._in_a_python_method:
            return False

        # cursor must be on last line
        if self.index("insert lineend") != self.index("end - 1 char"):
            return True

        # Block if there is terminal output after the cursor.
        # The tag_nextrange method almost does this, but doesn't find ranges that contain the cursor.
        # The tag_prevrange finds those ranges but also other ranges we don't care about.
        if self.tag_nextrange("output", "insert"):
            return True

        range_containing_cursor = self.tag_prevrange("output", "insert")
        if range_containing_cursor:
            range_start, range_end = range_containing_cursor
            if self.compare("insert", "<", range_end):
                # The range contains at least one character that is after cursor.
                return True

        return False

    # Needs special handling to avoid deleting output.
    def _handle_backspace(self, event):
        if "output" not in self.tag_names("insert - 1 char"):
            self.delete("insert - 1 char", "insert")
        return "break"

    def handle_enter_press(self) -> str | None:
        if self._editing_should_be_blocked():
            return None

        self.mark_set("insert", "insert lineend")
        self.insert("end - 1 char", "\n")
        self.see("insert")

        # Find all characters on last line not tagged with "output".
        last_line_start = 'end - 1 char - 1 line'
        last_line_end = 'end - 2 chars'

        text_chunks = []
        tag_on = ('output' in self.tag_names(last_line_start))

        for action, tag_or_text, index in self.dump(last_line_start, last_line_end):
            if action == 'tagon' and tag_or_text == 'output':
                tag_on = True
            elif action == 'tagoff' and tag_or_text == 'output':
                tag_on = False
            elif action == 'text' and not tag_on:
                text_chunks.append(tag_or_text)


        return "".join(text_chunks)


class NoTerminalRunner:
    def __init__(self, master: tkinter.Misc) -> None:
        self.textwidget = TerribleTerminalEmulator(master)
        self.textwidget.tag_config("output", background="gray")
        self.textwidget.bind("<Destroy>", partial(self.stop_executor, quitting=True), add=True)
        self.textwidget.bind("<Control-D>", self._handle_end_of_input)
        self.textwidget.bind("<Control-d>", self._handle_end_of_input)
        self.textwidget.bind("<Return>", self._feed_line_to_stdin)

        self.textwidget.tag_config("link", underline=True)
        self.executor: Executor | None = None

        button_frame = tkinter.Frame(self.textwidget)
        button_frame.place(relx=1, rely=0, anchor="ne")

    def _feed_line_to_stdin(self, event):
        if self.executor is not None:
            input_line = self.textwidget.handle_enter_press()
            if input_line is not None:
                # TODO: which encoding to use?
                self.executor.write_to_stdin((input_line + os.linesep).encode("utf-8"))
        return "break"

    def _handle_end_of_input(self, event):
        if self.executor is not None:
            self.executor.close_stdin()

    def stop_executor(self, junk_event: object = None, *, quitting: bool = False) -> None:
        if self.executor is not None:
            self.executor.stop(quitting=quitting)

    def run_command(self, cwd: Path, command: str) -> None:
        if self.executor is not None:
            # This prevents a bug where smashing F5 runs in parallel
            if not self.executor.started:
                return

            self.executor.stop()

        self.textwidget.delete("1.0", "end")

        self.executor = Executor(cwd, self.textwidget)
        self.executor.run(command)


def main():
    root = tkinter.Tk()
    runner = NoTerminalRunner(root)
    runner.textwidget.pack()
    runner.textwidget.focus()
    runner.run_command(Path("."), "python3 -i")
    root.mainloop()


main()
