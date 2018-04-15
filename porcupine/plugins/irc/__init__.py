from porcupine import actions, get_main_window, get_tab_manager, tabs
from . import connectdialog, gui


class IrcTab(tabs.Tab):

    def __init__(self, manager, irc_core):
        super().__init__(manager)
        self.irc_core = irc_core
        self.title = "IRC: %s" % irc_core.host

        self.irc_widget = gui.IrcWidget(self, irc_core, (lambda: None))
        self.irc_widget.pack(fill='both', expand=True)
        self.irc_widget.handle_events()

        self.bind('<Destroy>',
                  lambda event: self.irc_widget.part_all_channels_and_quit(),
                  add=True)

    # TODO: display e.g. (1) for a new message in the title
    # TODO: get_state() and from_state()?

    def on_focus(self):
        self.irc_widget.focus_the_entry()


def open_irc():
    irc_core = connectdialog.run(get_main_window())
    if irc_core is not None:    # not cancelled
        get_tab_manager().add_tab(IrcTab(get_tab_manager(), irc_core))


def setup():
    actions.add_command('IRC/Chat in IRC', open_irc)
