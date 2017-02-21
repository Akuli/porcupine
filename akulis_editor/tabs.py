r"""Tabs as in browser tabs, not \t characters.

Yes, I am aware of ttk.Notebook but it's simply way too limited for my
needs. I can't even change the color of the top label.
"""

import os
import tkinter as tk


def iter_children(widget):
    """Return an iterator of widget's children, recursively."""
    for child in widget.winfo_children():
        yield child
        yield from iter_children(child)


_close_image = None


class Tab:
    """A tab that can be added to TabManager."""

    def __init__(self):
        """Initialize the tab.

        labeltext will be the text of the top label.
        """
        self.topframe = None
        self.label = None
        self.content = None

    def create_widgets(self, tabmanager):
        """Create the top frame and the content frame."""
        global _close_image
        if _close_image is None:
            here = os.path.dirname(os.path.abspath(__file__))
            _close_image = tk.PhotoImage(
                file=os.path.join(here, 'data', 'closebutton.png'))

        def select_me(event):
            tabmanager.current_tab = self

        def close_me(event):
            tabmanager.close_tab(self)

        self.topframe = tk.Frame(tabmanager.topframeframe, relief='raised',
                                 border=1, padx=10, pady=3)
        self.topframe.bind('<Button-1>', select_me)

        self.label = tk.Label(self.topframe)
        self.label.pack(side='left')
        self.label.bind('<Button-1>', select_me)

        self.content = tk.Frame(tabmanager)

        # The image needs to be attached to self to avoid garbage
        # collection.
        closebutton = tk.Label(self.topframe, image=_close_image)
        closebutton.pack(side='left')
        closebutton.bind('<Button-1>', close_me)

    def can_be_closed(self):
        """Check if this tab can be closed.

        This always returns True by default. You can override this in a
        subclass.
        """
        return True

    def focus(self):
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
        self.topframeframe = tk.Frame(self)
        self.topframeframe.pack(fill='x')
        self._bind_wheel(self.topframeframe)
        self.tabs = []
        self.on_tabs_changed = []   # these are called like callback(tablist)
        self._current_tab = None
        self.no_tabs_frame = tk.Frame(self)
        self.no_tabs_frame.pack(fill='both', expand=True)

    @property
    def current_tab(self):
        return self._current_tab

    @current_tab.setter
    def current_tab(self, tab):
        if self.current_tab is None:
            self.no_tabs_frame.pack_forget()
        else:
            self.current_tab.topframe['relief'] = 'raised'
            self.current_tab.content.pack_forget()

        if tab is None:
            self.no_tabs_frame.pack(fill='both', expand=True)
        else:
            tab.topframe['relief'] = 'sunken'
            tab.content.pack(fill='both', expand=True)
            tab.focus()
        self._current_tab = tab

    @property
    def current_index(self):
        return self.tabs.index(self.current_tab)

    @current_index.setter
    def current_index(self, index):
        self.current_tab = self.tabs[index % len(self.tabs)]

    def do_tabs_changed(self):
        for callback in self.on_tabs_changed:
            callback(self.tabs)

    def add_tab(self, tab):
        """Add a Tab and add it to the end.

        Note that a tab can be added only once.
        """
        tab.create_widgets(self)
        assert tab.content is not None
        tab.topframe.grid(row=0, column=len(self.tabs))
        self.tabs.append(tab)

        self._bind_wheel(tab.topframe)
        for widget in iter_children(tab.topframe):
            self._bind_wheel(widget)

        if self.current_tab is None:
            # this is the first tab
            self.current_tab = tab

        self.do_tabs_changed()
        return tab

    def remove_tab(self, tab):
        """Remove a tab added with add_tab().

        The tab's closechecker is not called. Use the tab's close()
        method if you want to call it.
        """
        if tab is self.current_tab:
            # go to next or previous tab if possible, otherwise unselect
            # the tab
            if not (self.select_right() or self.select_left()):
                self.current_tab = None

        tab.content.pack_forget()
        tab.topframe.grid_forget()

        # the grid columns of topframes of tabs after this change, so we
        # need to take care of that
        where = self.tabs.index(tab)
        del self.tabs[where]
        for i in range(where, len(self.tabs)):
            self.tabs[i].topframe.grid(column=i)

        self.do_tabs_changed()

    def close_tab(self, tab):
        if tab.can_be_closed():
            self.remove_tab(tab)
            return True
        return False

    def select_left(self, *, roll_over=False):
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

    def select_right(self, *, roll_over=False):
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
        tab1.topframe.grid(column=index2)
        tab2.topframe.grid(column=index1)
        self.tabs[index1] = tab2
        self.tabs[index2] = tab1
        self.do_tabs_changed()

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


if __name__ == '__main__':
    # test/demo
    def do_ctrl_w(event):
        if tabmgr.current_tab is None:
            # no more tabs
            root.quit()
        else:
            tabmgr.close_tab(tabmgr.current_tab)

    def do_alt_n(event):
        if event.keysym in set('123456789'):
            index = int(event.keysym) - 1
            if index in range(len(tabmgr.tabs)):
                tabmgr.current_index = index

    root = tk.Tk()
    tabmgr = TabManager(root)
    tabmgr.pack(fill='both', expand=True)
    tabmgr.on_tabs_changed.append(print)
    tk.Label(tabmgr.no_tabs_frame, text="u have no open tabs :(").pack()

    root.bind_all('<Alt-Key>', do_alt_n)
    root.bind_all('<Control-Prior>',
                  lambda event: tabmgr.select_left(roll_over=True))
    root.bind_all('<Control-Next>',
                  lambda event: tabmgr.select_right(roll_over=True))
    root.bind_all('<Control-Shift-Prior>', lambda event: tabmgr.move_left())
    root.bind_all('<Control-Shift-Next>', lambda event: tabmgr.move_right())
    root.bind_all('<Control-w>', do_ctrl_w)

    for i in range(1, 6):
        tab = Tab()
        tabmgr.add_tab(tab)   # creates tab.label and tab.content
        tab.label['text'] = "tab %d" % i
        text = tk.Text(tab.content)
        text.pack()
        text.insert('1.0', "this is the content of tab %d" % i)

    root.mainloop()
