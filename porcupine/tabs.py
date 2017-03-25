r"""Tabs as in browser tabs, not \t characters.

Yes, I am aware of ttk.Notebook but it's simply way too limited for my
needs. I can't even change the color of the top label.
"""

import base64
import functools
import pkgutil
import tkinter as tk


class Tab:
    """A tab that can be added to TabManager."""

    def __init__(self, manager):
        self._manager = manager

        # the image needs to be attached to self to avoid garbage
        # collection
        data = pkgutil.get_data('porcupine', 'images/closebutton.gif')
        self._closeimage = tk.PhotoImage(
            format='gif', data=base64.b64encode(data))

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

        closebutton = tk.Label(self._topframe, image=self._closeimage)
        closebutton.pack(side='left')
        closebutton.bind('<Button-1>', lambda event: self.close())

        manager._bind_wheel(self._topframe)
        manager._bind_wheel(self.label)
        manager._bind_wheel(closebutton)

    def can_be_closed(self):
        """Check if this tab can be closed.

        This always returns True by default. You can override this in a
        subclass.
        """
        return True

    def close(self):
        """Remove this tab from the tab manager.

        This checks the return value of can_be_closed() and returns True
        if the tab was actually closed and False if not.
        """
        if self.can_be_closed():
            self._manager.remove_tab(self)
            return True
        return False

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
        self._on_x11 = (self.tk.call('tk', 'windowingsystem') == 'x11')

        # no, this is not a find/replace error, topframeframe is a frame
        # that contains topframes
        self._topframeframe = tk.Frame(self)
        self._topframeframe.pack(fill='x')
        self._bind_wheel(self._topframeframe)
        self.tabs = []
        self.on_tabs_changed = []   # these are called like callback(tablist)
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
        if tab is self._current_tab:
            return

        if self.current_tab is None:
            self.no_tabs_frame.pack_forget()
        else:
            self.current_tab._topframe['relief'] = 'raised'
            self.current_tab.content.pack_forget()

        if tab is None:
            self.no_tabs_frame.pack(fill='both', expand=True)
        else:
            tab._topframe['relief'] = 'sunken'
            tab.content.pack(fill='both', expand=True)
            tab.on_focus()
        self._current_tab = tab

    @property
    def current_index(self):
        return self.tabs.index(self.current_tab)

    @current_index.setter
    def current_index(self, index):
        self.current_tab = self.tabs[index % len(self.tabs)]

    def _do_tabs_changed(self):
        for callback in self.on_tabs_changed:
            callback(self.tabs)

    def add_tab(self, tab):
        """Add a Tab and add it to the end."""
        tab._topframe.grid(row=0, column=len(self.tabs))
        self.tabs.append(tab)

        if self.current_tab is None:
            # this is the first tab
            self.current_tab = tab

        self._do_tabs_changed()
        return tab

    def remove_tab(self, tab):
        """Remove a tab added with add_tab().

        The tab's can_be_closed() method is not called. Use the tab's
        close() method instead if you want to check if the tab can be
        closed.
        """
        if tab is self.current_tab:
            # go to next or previous tab if possible, otherwise unselect
            # the tab
            if not (self.select_right() or self.select_left()):
                self.current_tab = None

        tab.content.pack_forget()
        tab._topframe.grid_forget()

        # the grid columns of topframes of tabs after this change, so we
        # need to take care of that
        where = self.tabs.index(tab)
        del self.tabs[where]
        for i in range(where, len(self.tabs)):
            self.tabs[i]._topframe.grid(column=i)

        self._do_tabs_changed()

    def select_left(self, roll_over=False):
        """Switch to the tab at left if possible.

        If roll_over is True and the current tab is the first tab in
        this widget, switch to the last tab. Return True if the current
        tab was changed.
        """
        if len(self.tabs) < 2:
            return False
        if self.current_index == 0 and not roll_over:
            return False
        self.current_index -= 1
        return True

    def select_right(self, roll_over=False):
        """Like select_left(), but switch to the tab at right."""
        if len(self.tabs) < 2:
            return False
        if self.current_index == len(self.tabs)-1 and not roll_over:
            return False
        self.current_index += 1
        return True

    def _swap(self, index1, index2):
        """Swap two tabs with each other by indexes."""
        # Tk allows gridding multiple widgets in the same place, and
        # gridding an already gridded widget moves it.
        tab1 = self.tabs[index1]
        tab2 = self.tabs[index2]
        tab1._topframe.grid(column=index2)
        tab2._topframe.grid(column=index1)
        self.tabs[index1] = tab2
        self.tabs[index2] = tab1
        self._do_tabs_changed()

    def move_left(self):
        """Move the current tab left if possible.

        Return True if the tab was moved.
        """
        if len(self.tabs) < 2 or self.current_index == 0:
            return False
        self._swap(self.current_index, self.current_index-1)
        return True

    def move_right(self):
        """Move the current tab right if possible.

        Return True if the tab was moved.
        """
        if len(self.tabs) < 2 or self.current_index == len(self.tabs)-1:
            return False
        self._swap(self.current_index, self.current_index+1)
        return True

    # i needed to cheat with this and use stackoverflow, the man
    # pages don't say what OSX does with MouseWheel events and i
    # don't have an up-to-date OSX :(
    # http://stackoverflow.com/a/17457843
    def _bind_wheel(self, widget):
        if self._on_x11:
            widget.bind('<Button-4>', self._on_wheel)
            widget.bind('<Button-5>', self._on_wheel)
        else:
            widget.bind('<MouseWheel>', self._on_wheel)

    def _on_wheel(self, event):
        if self._on_x11:
            if event.num == 4:
                self.select_left()
            else:
                self.select_right()
        else:
            if event.delta > 0:
                self.select_left()
            else:
                self.select_right()

    def on_alt_n(self, event):
        """Select the n'th tab (1 <= n <= 9) based on event.keysym.

        Return 'break' if event.keysym was useful for this and None if
        nothing was done.
        """
        try:
            index = int(event.keysym) - 1
        except ValueError:
            return None

        if index in range(len(self.tabs)):
            self.current_index = index
            return 'break'
        return None

    def _on_ctrl_w(self):
        if self.current_tab is not None:
            self.current_tab.close()


if __name__ == '__main__':
    # test/demo
    root = tk.Tk()
    tabmgr = TabManager(root)
    tabmgr.pack(fill='both', expand=True)
    tabmgr.on_tabs_changed.append(print)
    tk.Label(tabmgr.no_tabs_frame, text="u have no open tabs :(").pack()

    for keysym, callback in tabmgr.bindings:
        root.bind_all(keysym, (lambda event: callback()))
    root.bind_all('<Alt-Key>', tabmgr.on_alt_n)

    for i in range(1, 6):
        tab = Tab(tabmgr)
        tab.label['text'] = "tab %d" % i
        text = tk.Text(tab.content)
        text.pack()
        text.insert('1.0', "this is the content of tab %d" % i)
        tabmgr.add_tab(tab)

    root.mainloop()
