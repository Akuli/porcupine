"""Run commands within the Porcupine window."""

import logging
import queue
import subprocess
import threading
import tkinter

from porcupine import get_tab_manager, images, utils

log = logging.getLogger(__name__)


class NoTerminalRunner:

    def __init__(self, master):
        # TODO: better coloring
        self.textwidget = tkinter.Text(master, height=12, state='disabled')
        self.textwidget.tag_config('info', foreground='blue')
        self.textwidget.tag_config('output')    # use default colors
        self.textwidget.tag_config('error', foreground='red')

        self._output_queue = queue.Queue()
        self._running_process = None
        self._queue_clearer()

    def _runner_thread(self, workingdir, command, succeeded_callback):
        process = None

        def emit_message(kind, msg):
            if process is not None and self._running_process is not process:
                # another _run_command() is already running
                return
            self._output_queue.put((kind, msg))

        emit_message('clear', None)
        emit_message('info', ' '.join(map(utils.quote, command)) + '\n')

        try:
            process = self._running_process = subprocess.Popen(
                command, cwd=workingdir,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except OSError as e:
            emit_message('error', '%s: %s\n' % (type(e).__name__, e))
            log.debug("here's full traceback", exc_info=True)
            return

        for line in process.stdout:
            # TODO: is utf-8 the correct choice on all platforms?
            emit_message('output', line.decode('utf-8', errors='replace'))
        process.communicate()    # make sure process.returncode is set

        if process.returncode == 0:
            # can't do succeeded_callback() here because this is running
            # in a thread and succeeded_callback() does tkinter stuff
            emit_message('info', "The process completed successfully.")
            emit_message('run', succeeded_callback)
        else:
            emit_message('error', "The process failed with status %d."
                         % process.returncode)

    def run_command(self, *args):
        # this is a daemon thread because i don't care what the fuck
        # happens to it when python exits
        threading.Thread(target=self._runner_thread,
                         args=args, daemon=True).start()

    def _queue_clearer(self):
        items = []
        while True:
            try:
                items.append(self._output_queue.get(block=False))
            except queue.Empty:
                break

        if items:
            self.textwidget['state'] = 'normal'
            for message_kind, value in items:
                if message_kind == 'clear':
                    self.textwidget.delete('1.0', 'end')
                elif message_kind == 'run':
                    value()
                else:
                    # value is text and message_kind is a tag
                    self.textwidget.insert('end', value, message_kind)
            self.textwidget['state'] = 'disabled'

        self.textwidget.after(100, self._queue_clearer)

    def destroy(self, junk_event=None):
        self.textwidget.destroy()
        try:
            self._running_process.kill()
        except AttributeError:
            assert self._running_process is None


def do_nothing():
    pass


# str(tab) is the Tk widget path, guaranteed to be unique
_no_terminal_runners = {}       # {str(tab): NoTerminalRunner}


# succeeded_callback() will be ran from tkinter if the command returns 0
def run_command(workingdir, command, succeeded_callback=do_nothing):
    tab = get_tab_manager().select()
    try:
        runner = _no_terminal_runners[str(tab)]
    except KeyError:
        runner = NoTerminalRunner(tab.bottom_frame)
        _no_terminal_runners[str(tab)] = runner

        def on_close(event):
            runner.destroy()
            del _no_terminal_runners[str(tab)]

        closebutton = tkinter.Label(
            runner.textwidget, image=images.get('closebutton'), cursor='hand2')
        closebutton.bind('<Button-1>', on_close)
        closebutton.place(relx=1, rely=0, anchor='ne')

    runner.textwidget.pack(side='top', fill='x')
    runner.run_command(workingdir, command, succeeded_callback)
