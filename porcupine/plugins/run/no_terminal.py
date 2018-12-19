"""Run commands within the Porcupine window."""

import logging
import subprocess
import threading
import weakref

import pythotk as tk

from porcupine import get_tab_manager, images, utils

log = logging.getLogger(__name__)


class NoTerminalRunner:

    def __init__(self, master):
        # TODO: better coloring that follows the pygments theme
        self.textwidget = tk.Text(master, height=12, state='disabled')
        self.textwidget.get_tag('info')['foreground'] = 'blue'
        # 'output' tag uses default colors
        self.textwidget.get_tag('error')['foreground'] = 'red'

        self._running_process = None

    def thread_target_run(self, workingdir, command, succeeded_callback):
        process = None

        @tk.make_thread_safe
        def show_messages(*messages):
            # FIXME: how is this supposed to work?
            if process is not None and self._running_process is not process:
                # another thread_target_run() is already running
                return

            self.textwidget.config['state'] = 'normal'
            for tag_or_clear, text in messages:
                if tag_or_clear == 'clear':
                    self.textwidget.delete(self.textwidget.start,
                                           self.textwidget.end)
                else:
                    tag_object = self.textwidget.get_tag(tag_or_clear)
                    self.textwidget.insert(self.textwidget.end, text,
                                           tag_object)
            self.textwidget.config['state'] = 'disabled'

        show_messages(
            ('clear', None),
            ('info', ' '.join(map(utils.quote, command)) + '\n'),
        )

        try:
            process = self._running_process = subprocess.Popen(
                command, cwd=workingdir,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except OSError as e:
            show_messages(
                ('error', '%s: %s\n' % (type(e).__name__, e)),
            )
            log.debug("error when running command without terminal",
                      exc_info=True)
            return

        for line in process.stdout:
            # TODO: is utf-8 the correct choice on all platforms?
            show_messages(
                ('output', line.decode('utf-8', errors='replace')),
            )
        process.communicate()    # make sure process.returncode is set

        if process.returncode == 0:
            # can't do succeeded_callback() here because this is running
            # in a thread and succeeded_callback() does tkinter stuff
            show_messages(('info', "The process completed successfully."))
            tk.make_thread_safe(succeeded_callback)()
        else:
            show_messages(('error', ("The process failed with status %d."
                                     % process.returncode)))

    def destroy(self, junk_event=None):
        self.textwidget.destroy()
        try:
            self._running_process.kill()
        except AttributeError:
            assert self._running_process is None


def do_nothing():
    pass


_no_terminal_runners = weakref.WeakKeyDictionary()    # {tab: NoTerminalRunner}


# succeeded_callback() will be ran from tkinter if the command returns 0
def run_command(workingdir, command, succeeded_callback=do_nothing):
    tab = get_tab_manager().selected_tab
    try:
        runner = _no_terminal_runners[tab]
    except KeyError:
        runner = NoTerminalRunner(tab.bottom_frame)
        _no_terminal_runners[tab] = runner

        def on_close():
            runner.destroy()
            del _no_terminal_runners[tab]

        closebutton = tk.Label(
            runner.textwidget, image=images.get('closebutton'), cursor='hand2')
        closebutton.bind('<Button-1>', on_close)
        closebutton.place(relx=1, rely=0, anchor='ne')

    runner.textwidget.pack(side='top', fill='x')

    # this is a daemon thread because i don't care what the fuck
    # happens to it when python exits
    threading.Thread(target=runner.thread_target_run,
                     args=[workingdir, command, succeeded_callback],
                     daemon=True).start()
