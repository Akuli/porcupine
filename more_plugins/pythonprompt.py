"""Use Python's >>> prompt inside Porcupine."""

# FIXME: >>> while True: print("lel")   (avoid making it as slow as idle is)
# FIXME: prevent writing anywhere except to the end of the prompt
# TODO: test this on windows, this may turn out to be pretty broken :(

import io
import queue
import signal
import subprocess
import sys
import threading
import tkinter
from tkinter import ttk
from typing import Any, Callable, Tuple, Union

from porcupine import get_tab_manager, menubar, tabs, textwidget, utils


def _tupleindex(index: str) -> Tuple[int, int]:
    """Convert 'line.column' to (line, column)."""
    line, column = index.split('.')
    return (int(line), int(column))


class PythonPrompt:
    def __init__(self, textwidget: tkinter.Text, close_callback: Callable[[], None]):
        self.widget = textwidget
        self.close_callback = close_callback
        self.widget.bind('<Return>', self._on_return, add=True)
        self.widget.bind('<<PythonPrompt:KeyboardInterrupt>>', self._keyboard_interrupt, add=True)
        self.widget.bind('<<PythonPrompt:Copy>>', self._copy, add=True)
        self.widget.bind('<<PythonPrompt:Clear>>', self._clear, add=True)
        self.widget.bind('<<PythonPrompt:SendEOF>>', self._send_eof, add=True)

        # without -u python buffers stdout and everything is one enter
        # press late :( see python --help
        self.process = subprocess.Popen(
            [sys.executable, '-i', '-u'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )

        # the queuer thread is a daemon thread because it makes exiting
        # porcupine easier and interrupting it isn't a problem
        self._queue: queue.Queue[Tuple[str, Union[int, bytes]]] = queue.Queue()
        threading.Thread(target=self._queuer, daemon=True).start()
        self.widget.after_idle(self._queue_clearer)

    def _keyboard_interrupt(self, junk: object) -> None:
        try:
            self.process.send_signal(signal.SIGINT)
        except ProcessLookupError:
            # the subprocess has terminated, _queue_clearer should have
            # taken care of it already
            assert self.widget['state'] == 'disabled'

    def _copy(self, junk: object) -> None:
        # i didn't find a way to do this like tkinter does it by default
        try:
            start, end = self.widget.tag_ranges('sel')
        except ValueError:
            return

        text = self.widget.get(start, end)
        if text:
            self.widget.clipboard_clear()
            self.widget.clipboard_append(text)

    def _clear(self, junk: object) -> None:
        self.widget.delete('1.0', 'end-1l')

    def _send_eof(self, junk: object) -> None:
        assert self.process.stdin is not None
        self.process.stdin.close()

    def _on_return(self, junk: object) -> utils.BreakOrNone:
        end_of_output = _tupleindex(str(self.widget.tag_ranges('output')[-1]))
        cursor = _tupleindex(self.widget.index('insert'))
        end = _tupleindex(self.widget.index('end - 1 char'))

        # (line, column) tuples compare nicely
        if not (end_of_output <= cursor <= end):
            return 'break'

        # this happens when inputting multiple lines at once
        if end_of_output[0] < cursor[0]:
            end_of_output = (cursor[0], 0)

        # this needs to return 'break' to allow pressing enter with the
        # cursor anywhere on the line
        text = self.widget.get('%d.%d' % end_of_output, 'end')  # ends with \n
        self.widget.insert('end', '\n')
        self.widget.mark_set('insert', 'end')
        assert self.process.stdin is not None
        self.process.stdin.write(text.encode('utf-8'))
        self.process.stdin.flush()
        return 'break'

    def _queuer(self) -> None:
        while True:
            assert self.process.stdout is not None
            output = self.process.stdout.read(io.DEFAULT_BUFFER_SIZE)
            if not output:
                # the process terminated, wait() will return the exit
                # code immediately instead of actually waiting
                self._queue.put(('exit', self.process.wait()))
                break
            self._queue.put(('output', output))

    def _queue_clearer(self) -> None:
        try:
            state, value = self._queue.get(block=False)
        except queue.Empty:
            # nothing there right now, let's come back later
            self.widget.after(50, self._queue_clearer)
            return

        if state == 'exit':
            if value == 0:
                # success
                self.close_callback()
            else:
                self.widget.insert(
                    'end', f"\n\n***********************\nthe subprocess exited with code {value!r}"
                )
                self.widget.config(state='disabled')
            return

        assert state == 'output' and isinstance(value, bytes)
        if sys.platform == 'win32':
            value = value.replace(b'\r\n', b'\n')
        self.widget.insert('end-1c', value.decode('utf-8', errors='replace'), 'output')
        self.widget.see('end-1c')

        # we got something, let's try again as soon as possible
        self.widget.after_idle(self._queue_clearer)


class PromptTab(tabs.Tab):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.title_choices = ["Interactive Prompt"]

        self.textwidget = tkinter.Text(self, width=1, height=1)
        self.textwidget.pack(side='left', fill='both', expand=True)
        textwidget.use_pygments_theme(self.textwidget)
        self.prompt = PythonPrompt(self.textwidget, (lambda: self.master.close_tab(self)))

        self.scrollbar = ttk.Scrollbar(self)
        self.scrollbar.pack(side='left', fill='y')
        self.textwidget.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.textwidget.yview)

        self.bind('<<TabSelected>>', (lambda event: self.textwidget.focus()), add=True)
        self.bind('<Destroy>', self._on_destroy, add=True)

    def _on_destroy(self, junk: object) -> None:
        # TODO: what if terminating blocks? maybe a timeout and fall
        # back to killing?
        try:
            self.prompt.process.terminate()
        except ProcessLookupError:
            # it has been terminated already
            pass


def start_prompt() -> None:
    get_tab_manager().add_tab(PromptTab(get_tab_manager()))


def setup() -> None:
    menubar.get_menu("Run").add_command(label="Interactive Python prompt", command=start_prompt)
