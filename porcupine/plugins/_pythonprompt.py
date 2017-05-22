"""A tab that displays a >>> prompt.

This plugin is disabled by default because sending a Ctrl+C ,to a
subprocess is basically impossible on Windows and interrupts. If you
don't use Windows, rename this to _pythonprompt and have fun with it :)
"""

# FIXME: >>> while True: print("lel")
# TODO: test this on windows, this may turn out to be pretty broken :(

import io
import platform
import queue
import signal
import subprocess
import sys
import threading
import tkinter as tk

from porcupine import tabs, textwidget, utils


_WINDOWS = (platform.system() == 'Windows')


def _tupleindex(index):
    """Convert 'line.column' to (line, column)."""
    line, column = index.split('.')
    return (int(line), int(column))


class PythonPrompt:

    def __init__(self, textwidget, close_callback):
        self.widget = textwidget
        self.close_callback = close_callback
        self.widget.bind('<Return>', self._on_return)
        self.widget.bind('<Control-c>', self._keyboard_interrupt)
        self.widget.bind('<Control-C>', self._copy)
        self.widget.bind('<Control-l>', self._clear)
        self.widget.bind('<Control-L>', self._clear)
        self.widget.bind('<Control-d>', self._send_eof)
        self.widget.bind('<Control-D>', self._send_eof)

        # without -u python buffers stdout and everything is one enter
        # press late :( see python --help
        self.process = subprocess.Popen(
            [sys.executable, '-i', '-u'], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)

        # the queuer thread is a daemon thread because it makes exiting
        # porcupine easier and interrupting it isn't a problem
        self._queue = queue.Queue()
        threading.Thread(target=self._queuer, daemon=True).start()
        self.widget.after_idle(self._queue_clearer)

    def _keyboard_interrupt(self, event):
        try:
            self.process.send_signal(signal.SIGINT)
        except ProcessLookupError:
            # the subprocess has terminated, _queue_clearer should have
            # taken care of it already
            assert self.widget['state'] == 'disabled'

    def _copy(self, event):
        # i didn't find a way to do this like tkinter does it by default
        try:
            start, end = self.widget.tag_ranges('sel')
        except ValueError:
            return

        text = self.widget.get(start, end)
        if text:
            self.widget.clipboard_clear()
            self.widget.clipboard_append(text)

    def _clear(self, event):
        self.widget.delete('1.0', 'end-1l')

    def _send_eof(self, event):
        self.process.stdin.close()

    def _on_return(self, event):
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
        text = self.widget.get('%d.%d' % end_of_output, 'end')   # ends with \n
        self.widget.insert('end', '\n')
        self.widget.mark_set('insert', 'end')
        self.process.stdin.write(text.encode('utf-8'))
        self.process.stdin.flush()
        return 'break'

    def _queuer(self):
        while True:
            output = self.process.stdout.read(io.DEFAULT_BUFFER_SIZE)
            if not output:
                # the process terminated, wait() will return the exit
                # code immediately instead of actually waiting
                self._queue.put(('exit', self.process.wait()))
                break
            self._queue.put(('output', output))

    def _queue_clearer(self):
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
                    'end', "\n\n***********************\n" +
                    "the subprocess exited with code %d" % value)
                self.widget['state'] = 'disabled'
            return

        assert state == 'output'
        if _WINDOWS:
            value = value.replace(b'\r\n', b'\n')
        self.widget.insert(
            'end-1c', value.decode('utf-8', errors='replace'), 'output')
        self.widget.see('end-1c')

        # we got something, let's try again as soon as possible
        self.widget.after_idle(self._queue_clearer)


class PromptTab(tabs.Tab):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.label['text'] = "Interactive Prompt"

        self.textwidget = textwidget.ThemedText(
            self.content, width=1, height=1)
        self.textwidget.pack(side='left', fill='both', expand=True)
        self.prompt = PythonPrompt(self.textwidget, self.close)

        self.scrollbar = tk.Scrollbar(self.content)
        self.scrollbar.pack(side='left', fill='y')
        self.textwidget['yscrollcommand'] = self.scrollbar.set
        self.scrollbar['command'] = self.textwidget.yview

    def on_focus(self):
        self.textwidget.focus()

    def close(self):
        super().close()

        # TODO: what if terminating blocks? maybe a timeout and fall
        # back to killing?
        try:
            self.prompt.process.terminate()
        except ProcessLookupError:
            # it has been terminated already
            pass


def setup(editor):
    def start_prompt():
        tab = PromptTab(editor.tabmanager)
        utils.copy_bindings(editor, tab.textwidget)
        editor.tabmanager.add_tab(tab)
        editor.tabmanager.current_tab = tab

    editor.add_action(start_prompt, "Run/Interactive Prompt",
                      "Ctrl+I", "<Control-i>")
