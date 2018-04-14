import enum
import tkinter
from tkinter import ttk


# represents the server, a channel or a PM conversation
class ChannelLike:

    # userlist is None if this is not a channel
    # name is a nick or channel name, or None if this is the first
    # ChannelLike ever created, used for server messages
    def __init__(self, ircwidget, name, users=None):
        # if someone changes nick, IrcWidget takes care of updating .name
        self.name = name

        # width and height are minimums
        # IrcWidget's pack lets this stretch
        self.textwidget = tkinter.Text(ircwidget, width=1, height=1)

        if users is None:
            self.userlist = None
            self.userlistbox = None
        else:
            # why is there no ttk listbox :(
            # bigpanedw adds this to itself when needed
            self.userlist = list(users)
            self.userlistbox = tkinter.Listbox(ircwidget, width=15)
            self.userlistbox.insert('end', *self.userlist)


class IrcWidget(ttk.PanedWindow):

    def __init__(self, master, nick, **kwargs):
        kwargs.setdefault('orient', 'horizontal')
        super().__init__(master, **kwargs)
        self.nick = nick

        self.channel_likes = {}   # {channel_like.name: channel_like}
        self.current_channel_like = None   # selected in self.channel_selector

        self.channel_selector = tkinter.Listbox(self, width=15)
        self.channel_selector.bind('<<ListboxSelect>>', self._on_selection)
        self.add(self.channel_selector, weight=0)   # don't stretch

        self._middle_pane = ttk.Frame(self)
        self.add(self._middle_pane, weight=1)    # always stretch

        entryframe = ttk.Frame(self._middle_pane)
        entryframe.pack(side='bottom', fill='x')
        ttk.Label(entryframe, text=nick).pack(side='left')
        entry = ttk.Entry(entryframe)
        entry.pack(side='left', fill='x', expand=True)

    def _select_index(self, index):
        self.channel_selector.selection_clear(0, 'end')
        self.channel_selector.selection_set(index)
        self.channel_selector.event_generate('<<ListboxSelect>>')

    def add_channel_like(self, channel_like):
        assert channel_like.name not in self.channel_likes
        self.channel_likes[channel_like.name] = channel_like

        if channel_like.name is None:
            # the special server channel-like
            assert len(self.channel_likes) == 1
            self.channel_selector.insert('end', "The Server")
        else:
            self.channel_selector.insert('end', channel_like.name)
        self._select_index('end')

    def remove_channel_like(self, channel_like):
        del self.channel_likes[channel_like.name]

        # i didn't find a better way to delete a listbox item by name
        index = self.channel_selector.get(0, 'end').index(channel_like.name)
        was_last = (index == len(self.channel_likes) - 1)
        was_selected = (index in self.channel_selector.curselection())

        # must be after the index stuff above
        self.channel_selector.delete(index)

        if was_selected:
            # select another item instead
            if was_last:
                self._select_index('end')
            else:
                # there's an item after the item that got deleted
                # after deleting, the indexes are shifted by 1, so this
                # selects the element after the deleted element
                self._select_index(index)

    # this must be called when someone that the user is PM'ing with
    # changes nick
    # channels and the special server channel-like can't be renamed
    def rename_channel_like(self, old_name, new_name):
        self.channel_likes[new_name] = self.channel_likes.pop(old_name)
        self.channel_likes[new_name].name = new_name

        index = self.channel_selector.get(0, 'end').index(old_name)
        was_selected = (index in self.channel_selector.curselection())
        self.channel_selector.delete(index)
        self.channel_selector.insert(index, new_name)
        if was_selected:
            self._select_index('end')

    def _on_selection(self, event):
        (index,) = self.channel_selector.curselection()
        if index == 0:   # the special server channel-like
            new_channel_like = self.channel_likes[None]
        else:
            new_channel_like = self.channel_likes[self.channel_selector.get(
                index)]   # pep8 line length makes for weird-looking code

        if self.current_channel_like is new_channel_like:
            return

        if self.current_channel_like is not None:
            # not running for the first time
            if self.current_channel_like.userlistbox is not None:
                self.remove(self.current_channel_like.userlistbox)
            self.current_channel_like.textwidget.pack_forget()

        new_channel_like.textwidget.pack(
            in_=self._middle_pane, side='top', fill='both', expand=True)
        if new_channel_like.userlistbox is not None:
            self.add(new_channel_like.userlistbox, weight=0)

        self.current_channel_like = new_channel_like


if __name__ == '__main__':
    root = tkinter.Tk()
    ircwidget = IrcWidget(root, 'asd')
    ircwidget.pack(fill='both', expand=True)

    ircwidget.add_channel_like(ChannelLike(ircwidget, None))
    lol = ChannelLike(ircwidget, "##lol", ['a', 'b'])
    ircwidget.add_channel_like(lol)
    ircwidget.add_channel_like(ChannelLike(ircwidget, "##asd", ['x', 'y']))
    ircwidget.rename_channel_like('##lol', '##loooool')
    ircwidget.rename_channel_like('##asd', '##asdfghj')

    root.mainloop()
