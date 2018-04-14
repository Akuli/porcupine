import enum
import queue
import time
import tkinter
from tkinter import ttk

import backend


# represents the server, a channel or a PM conversation
class ChannelLike:

    # users is None if this is not a channel
    # name is a nick or channel name, or None if this is the first
    # ChannelLike ever created, used for server messages
    def __init__(self, ircwidget, name, users=None):
        # if someone changes nick, IrcWidget takes care of updating .name
        self.name = name

        # width and height are minimums
        # IrcWidget packs this and lets this stretch
        self.textwidget = tkinter.Text(ircwidget, width=1, height=1,
                                       state='disabled')

        if users is None:
            self._userlist = None
            self.userlistbox = None
        else:
            # why is there no ttk listbox :(
            # bigpanedw adds this to itself when needed
            self._userlist = list(users)
            self.userlistbox = tkinter.Listbox(ircwidget, width=15)
            self.userlistbox.insert('end', *self._userlist)

    def add_message(self, sender, message):
        now = time.strftime('%H:%M')
        self.textwidget['state'] = 'normal'
        self.textwidget.insert(
            'end', '[%s] %15s | %s\n' % (now, sender, message))
        self.textwidget['state'] = 'disabled'


class IrcWidget(ttk.PanedWindow):

    def __init__(self, master, irc_core, on_quit, **kwargs):
        kwargs.setdefault('orient', 'horizontal')
        super().__init__(master, **kwargs)
        self._core = irc_core
        self._on_quit = on_quit

        self._channel_likes = {}   # {channel_like.name: channel_like}
        self._current_channel_like = None  # selected in self._channel_selector

        self._channel_selector = tkinter.Listbox(self, width=15)
        self._channel_selector.bind('<<ListboxSelect>>', self._on_selection)
        self.add(self._channel_selector, weight=0)   # don't stretch

        self._middle_pane = ttk.Frame(self)
        self.add(self._middle_pane, weight=1)    # always stretch

        entryframe = ttk.Frame(self._middle_pane)
        entryframe.pack(side='bottom', fill='x')
        ttk.Label(entryframe, text=irc_core.nick).pack(side='left')
        entry = ttk.Entry(entryframe)
        entry.pack(side='left', fill='x', expand=True)

    def _select_index(self, index):
        self._channel_selector.selection_clear(0, 'end')
        self._channel_selector.selection_set(index)
        self._channel_selector.event_generate('<<ListboxSelect>>')

    def add_channel_like(self, channel_like):
        assert channel_like.name not in self._channel_likes
        self._channel_likes[channel_like.name] = channel_like

        if channel_like.name is None:
            # the special server channel-like
            assert len(self._channel_likes) == 1
            self._channel_selector.insert('end', self._core.host)
        else:
            self._channel_selector.insert('end', channel_like.name)
        self._select_index('end')

    def remove_channel_like(self, channel_like):
        del self._channel_likes[channel_like.name]

        # i didn't find a better way to delete a listbox item by name
        index = self._channel_selector.get(0, 'end').index(channel_like.name)
        was_last = (index == len(self._channel_likes) - 1)
        was_selected = (index in self._channel_selector.curselection())

        # must be after the index stuff above
        self._channel_selector.delete(index)

        if was_selected:
            # select another item instead
            if was_last:
                self._select_index('end')
            else:
                # deleting shifts indexes by 1, so this selects the
                # element after the deleted element
                self._select_index(index)

    # this must be called when someone that the user is PM'ing with
    # changes nick
    # channels and the special server channel-like can't be renamed
    def rename_channel_like(self, old_name, new_name):
        self._channel_likes[new_name] = self._channel_likes.pop(old_name)
        self._channel_likes[new_name].name = new_name

        index = self._channel_selector.get(0, 'end').index(old_name)
        was_selected = (index in self._channel_selector.curselection())
        self._channel_selector.delete(index)
        self._channel_selector.insert(index, new_name)
        if was_selected:
            self._select_index('end')

    def _on_selection(self, event):
        (index,) = self._channel_selector.curselection()
        if index == 0:   # the special server channel-like
            new_channel_like = self._channel_likes[None]
        else:
            new_channel_like = self._channel_likes[self._channel_selector.get(
                index)]   # pep8 line length makes for weird-looking code

        if self._current_channel_like is new_channel_like:
            return

        if self._current_channel_like is not None:
            # not running for the first time
            if self._current_channel_like.userlistbox is not None:
                self.remove(self._current_channel_like.userlistbox)
            self._current_channel_like.textwidget.pack_forget()

        new_channel_like.textwidget.pack(
            in_=self._middle_pane, side='top', fill='both', expand=True)
        if new_channel_like.userlistbox is not None:
            self.add(new_channel_like.userlistbox, weight=0)

        self._current_channel_like = new_channel_like

    def handle_events(self):
        while True:
            try:
                event, *event_args = self._core.event_queue.get(block=False)
            except queue.Empty:
                break

            if event == backend.IrcEvent.server_message:
                server, command, args = event_args
                ircwidget._channel_likes[None].add_message(
                    server, ' '.join(args))

            elif event == backend.IrcEvent.self_quit:
                self._on_quit()

            else:
                raise ValueError("unknown event type " + repr(event))

        self.after(100, self.handle_events)


if __name__ == '__main__':
    core = backend.IrcCore('chat.freenode.net', 6667, 'testieeeeeeeeeee')
    core.connect()

    root = tkinter.Tk()
    ircwidget = IrcWidget(root, core, root.destroy)
    ircwidget.pack(fill='both', expand=True)
    ircwidget.add_channel_like(ChannelLike(ircwidget, None))
    ircwidget.handle_events()

    root.mainloop()
