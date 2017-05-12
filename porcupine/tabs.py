r"""Tabs as in browser tabs, not \t characters.

Yes, I am aware of ttk.Notebook but it's simply way too limited for my
needs. I can't even change the color of the top label.

The filetabs.FileTab class inherits from the Tab class in this module.
This is less God-objecty than dumping everything into one class, and
it's easier to debug the code.
"""

import functools
import tkinter as tk

from porcupine import utils


class Tab:
    """A tab that can be added to TabManager."""

    def __init__(self, manager):
        self._manager = manager

        def select_me(event):
            manager.current_tab = self

        self._topframe = tk.Frame(manager._topframeframe, relief='raised',
                                  border=1, padx=10, pady=3)
        self._topframe.bind('<Button-1>', select_me)

        self.label = tk.Label(self._topframe)
        self.label.pack(side='left')
        self.label.bind('<Button-1>', select_me)

        # Subclasses can add stuff here.
        self.content = tk.Frame(manager)

        def _close_if_can(event):
            if self.can_be_closed():
                self.close()

        closebutton = tk.Label(
            self._topframe, image=utils.get_image('closebutton.gif'))
        closebutton.pack(side='left')
        closebutton.bind('<Button-1>', _close_if_can)

        utils.bind_mouse_wheel(self._topframe, manager._on_wheel)
        utils.bind_mouse_wheel(self.label, manager._on_wheel)
        utils.bind_mouse_wheel(closebutton, manager._on_wheel)

    def can_be_closed(self):
        """Check if this tab can be closed.

        This always returns True by default. You can override this in a
        subclass.
        """
        return True

    def close(self):
        """Remove this tab from the tab manager.

        Overrides must call super().
        """
        self._manager._remove_tab(self)
        self._topframe.destroy()
        self.content.destroy()

    def on_focus(self):
        """This is called when the tab is selected.

        This does nothing by default. You can override this in a
        subclass and make this focus the main widget if the tab has one.
        """


class TabManager(tk.Frame):
    """A simple but awesome tab widget.

    The tabs attribute is meant to be read-only. The results of
    modifying it are undefined.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # no, this is not a find/replace error, topframeframe is a frame
        # that contains topframes
        self._topframeframe = tk.Frame(self)
        self._topframeframe.pack(fill='x')
        utils.bind_mouse_wheel(self._topframeframe, self._on_wheel)
        self.tabs = []
        self.new_tab_hook = utils.ContextManagerHook(__name__)
        self.tab_changed_hook = utils.CallbackHook(__name__)
        self._current_tab = None
        self.no_tabs_frame = tk.Frame(self)
        self.no_tabs_frame.pack(fill='both', expand=True)

        # These can be bound using bind_all(). Note that it's also
        # recommended to bind <Alt-Key> to on_alt_n, but it isn't bound
        # by default because it needs the event object that these other
        # callbacks don't need.
        self.bindings = [
            ('<Control-Prior>', functools.partial(self.select_left, True)),
            ('<Control-Next>', functools.partial(self.select_right, True)),
            ('<Control-Shift-Prior>', self.move_left),
            ('<Control-Shift-Next>', self.move_right),
            ('<Control-w>', self._on_ctrl_w),
        ]

    @property
    def current_tab(self):
        return self._current_tab

    @current_tab.setter
    def current_tab(self, tab):
        assert tab is None or tab in self.tabs
        if tab is self._current_tab:
            return

        # there's always a tab or no tabs message, let's hide it
        if self.current_tab is None:
            self.no_tabs_frame.pack_forget()
        else:
            self.current_tab._topframe['relief'] = 'raised'
            self.current_tab.content.pack_forget()

        # and then replace it with the new tab or no tabs message
        if tab is None:
            self.no_tabs_frame.pack(fill='both', expand=True)
        else:
            tab._topframe['relief'] = 'sunken'
            tab.content.pack(fill='both', expand=True)
            tab.on_focus()

        self._current_tab = tab
        self.tab_changed_hook.run(tab)

    @property
    def current_index(self):
        if self.current_tab is None:
            return None
        return self.tabs.index(self.current_tab)

    @current_index.setter
    def current_index(self, index):
        if index < 0:
            # this would create weird rollovers so maybe best to avoid
            raise IndexError
        self.current_tab = self.tabs[index]

    def add_tab(self, tab):
        tab._topframe.grid(row=0, column=len(self.tabs))
        self.tabs.append(tab)
        if self.current_tab is None:
            # this is the first tab
            self.current_tab = tab

        tab.__hook_context_manager = self.new_tab_hook.run(tab)
        tab.__hook_context_manager.__enter__()
        return tab

    def _remove_tab(self, tab):
        if tab is self.current_tab:
            # go to next or previous tab if there are other tabs,
            # otherwise unselect the tab
            if not (self.select_right() or self.select_left()):
                self.current_tab = None

        tab.__hook_context_manager.__exit__(None, None, None)
        tab.content.pack_forget()
        tab._topframe.grid_forget()

        # the grid columns of topframes of tabs after this change, so we
        # need to take care of that
        where = self.tabs.index(tab)
        del self.tabs[where]
        for i in range(where, len(self.tabs)):
            self.tabs[i]._topframe.grid(column=i)

    def _select_next_to(self, diff, roll_over):
        if len(self.tabs) < 2:
            return False

        if roll_over:
            self.current_index = (self.current_index + diff) % len(self.tabs)
            return True
        try:
            self.current_index += diff
            return True
        except IndexError:
            return False

    def select_left(self, roll_over=False):
        """Switch to the tab at left if possible.

        If roll_over is True and the current tab is the first tab in
        this widget, switch to the last tab. Return True if the current
        tab was changed.
        """
        return self._select_next_to(-1, roll_over)

    def select_right(self, roll_over=False):
        """Like select_left(), but switch to the tab at right."""
        return self._select_next_to(+1, roll_over)

    def _on_wheel(self, direction):
        diffs = {'up': -1, 'down': +1}
        self._select_next_to(diffs[direction], False)

    def _swap(self, i1, i2):
        self.tabs[i1], self.tabs[i2] = self.tabs[i2], self.tabs[i1]
        for i in (i1, i2):
            # tk allows gridding multiple widgets in the same place, and
            # gridding an already gridded widget moves it
            self.tabs[i]._topframe.grid(column=i)

    def move_left(self):
        """Move the current tab left if possible.

        Return True if the tab was moved.
        """
        if self.current_index in {None, 0}:
            return False
        self._swap(self.current_index, self.current_index-1)
        return True

    def move_right(self):
        """Like move_left(), but moves right."""
        if self.current_index in {None, len(self.tabs)-1}:
            return False
        self._swap(self.current_index, self.current_index+1)
        return True

    def on_alt_n(self, event):
        """Select the n'th tab (1 <= n <= 9) based on event.keysym.

        Return 'break' if event.keysym was useful for this and None if
        nothing was done.
        """
        try:
            self.current_index = int(event.keysym) - 1
            return 'break'
        except (IndexError, ValueError):
            return None

    def _on_ctrl_w(self):
        if self.current_tab is not None:
            self.current_tab.close()


if __name__ == '__main__':
    # test/demo
    root = tk.Tk()
    tabmgr = TabManager(root)
    tabmgr.pack(fill='both', expand=True)
    tabmgr.on_tab_changed.append(lambda tab: print(tab.label['text']))

    tk.Label(tabmgr.no_tabs_frame, text="u have no open tabs :(").pack()

    for keysym, callback in tabmgr.bindings:
        root.bind_all(keysym, (lambda event, c=callback: c()))
    root.bind_all('<Alt-Key>', tabmgr.on_alt_n)

    for i in range(1, 6):
        tab = Tab(tabmgr)
        tab.label['text'] = "tab %d" % i
        text = tk.Text(tab.content)
        text.pack()
        text.insert('1.0', "this is the content of tab %d" % i)
        tabmgr.add_tab(tab)

    root.mainloop()
