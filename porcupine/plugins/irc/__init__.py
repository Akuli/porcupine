from porcupine import actions, get_main_window, get_tab_manager, tabs
from . import connectdialog, gui


class IrcTab(tabs.Tab):

    def __init__(self, manager, irc_core):
        super().__init__(manager)

        self.irc_widget = gui.IrcWidget(self, irc_core, (lambda: None))
        self.irc_widget.pack(fill='both', expand=True)
        self.irc_widget.bind('<<NotSeenCountChanged>>', self._update_title)
        self._update_title()
        self.irc_widget.handle_events()

        self.bind('<Destroy>',
                  lambda event: self.irc_widget.part_all_channels_and_quit(),
                  add=True)
        manager.bind('<<NotebookTabChanged>>', self.on_current_tab_changed,
                     add=True)

    def _update_title(self, junk_event=None):
        title = "IRC: %s" % self.irc_widget.core.host
        number = self.irc_widget.not_seen_count()
        if number != 0:
            title = "(%d) %s" % (number, title)
        self.title = title

    def on_current_tab_changed(self, event):
        if event.widget.select() is self:      # the IRC tab was just selected
            self.irc_widget.current_channel_like_notify = False
            self.irc_widget.mark_seen()
        else:
            self.irc_widget.current_channel_like_notify = True

    # TODO: get_state() and from_state()?

    def on_focus(self):
        self.irc_widget.focus_the_entry()


def open_irc():
    irc_core = connectdialog.run(get_main_window())
    if irc_core is not None:    # not cancelled
        get_tab_manager().add_tab(IrcTab(get_tab_manager(), irc_core))


def setup():
    actions.add_command('IRC/Chat in IRC', open_irc)
