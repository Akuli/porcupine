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

        self.channel_likes = []
        self.current_channel_like = None

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

    def add_channel_like(self, channel_like):
        self.channel_likes.append(channel_like)

        if channel_like.name is None:
            # the special server channel-like
            assert len(self.channel_likes) == 1
            self.channel_selector.insert('end', "The Server")
        else:
            self.channel_selector.insert('end', channel_like.name)
        self.channel_selector.selection_clear(0, 'end')
        self.channel_selector.selection_set('end')
        self.channel_selector.event_generate('<<ListboxSelect>>')

    def remove_channel_like(self, channel_like):
        index = self.channel_likes.index(channel_like)
        was_last = (index == len(self.channel_likes) - 1)
        del self.channel_likes[index]
        self.channel_selector.delete(index)

        self.channel_selector.selection_clear(0, 'end')
        if was_last:
            self.channel_selector.selection_set('end')
        else:
            # there's an item after the item that got deleted
            # after deleting, the indexes are shifted by 1, so this selects
            # the element after the deleted element
            self.channel_selector.selection_set(index)
        self.channel_selector.event_generate('<<ListboxSelect>>')

    def _on_selection(self, event):
        (index,) = event.widget.curselection()
        new_channel_like = self.channel_likes[index]
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
#    import functools
#    big = ttk.Frame(tkinter.Tk())
#    big.pack(fill='both', expand=True)
#
#    lol = ttk.Label(big, text="lol")
#
#    def move(area):
#        lol.pack_forget()
#        lol.pack(in_=area)
#        lol.tkraise(area)     # make sure it's visible
#
#    area1 = ttk.Frame(big)
#    area1.pack(side='left', fill='both', expand=True)
#    area2 = ttk.Frame(big)
#    area2.pack(side='left', fill='both', expand=True)
#
#    ttk.Button(area1, text="asd", command=functools.partial(move, area1)).pack()
#    ttk.Button(area2, text="asd", command=functools.partial(move, area2)).pack()
#
#    tkinter.mainloop()

    root = tkinter.Tk()
    ircwidget = IrcWidget(root, 'asd')
    ircwidget.pack(fill='both', expand=True)

    ircwidget.add_channel_like(ChannelLike(ircwidget, None))
    lol = ChannelLike(ircwidget, "##lol", ['a', 'b'])
    ircwidget.add_channel_like(lol)
    ircwidget.add_channel_like(ChannelLike(ircwidget, "##asd", ['x', 'y']))
    ircwidget.remove_channel_like(lol)

    root.mainloop()
