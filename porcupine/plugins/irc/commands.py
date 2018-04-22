"""This file handles commands like /join."""

# command handlers can return (SHOW_MESSAGE, message) to display a
# message in the gui, nothing happens if the handler returns None
SHOW_MESSAGE = object()


# TODO: this stuff needs tests and seems easy enough to test
class CommandHandler:

    def __init__(self, core):
        self.irc_core = core
        self._commands = {}
        self._add_default_commands()

    # TODO: add_command('/echo <message>') would be great
    def add_command(self, name):
        """A decorator for adding commands.

        Example::

            @command_handler.add_command('/echo')
            def echo(message):
                if not message:
                    return (SHOW_MESSAGE, "Usage: /echo <message>")
                return (SHOW_MESSAGE, message)

        Use ``command_hander.irc_core`` to access the ``IrcCore`` object
        when needed::

            @command_handler.add_command('/join')
            def join(channel):
                if not channel:
                    return (SHOW_MESSAGE, "Usage: /join <channel>")
                command_handler.irc_core.join_channel(channel)
                return None

        Handler functions always take exactly 1 argument, and that's the
        command as a string without the ``'/echo '`` part. For example,
        ``/echo hello world`` would mean that ``message`` is
        ``'hello world'``, and a plain ``/echo`` would mean that
        ``message`` is an empty string. The ``if not message:`` part
        checks for that.

        The return value can be ``(SHOW_MESSAGE, message_string)`` to
        show a message in the GUI, or ``None`` to show no message.
        """
        if not name.startswith('/'):
            raise ValueError("%r is an invalid command name because command "
                             "names must start with '/'" % name)

        def do_it(func):
            self._commands[name] = func
            return func

        return do_it

    # TODO: something for adding more commands?
    def _add_default_commands(self):
        @self.add_command('/join')
        def join(channel):
            # plain '/join' for joining the current channel would be
            # useful if the user is kicked often, but that's unlikely
            # kicks are not handled yet anyway :(
            if not channel:
                return (SHOW_MESSAGE, "Usage: /join <channel>")
            self.irc_core.join_channel(channel)
            return None

        @self.add_command('/part')
        def part(channel):
            # TODO: plain '/part' to part from the current channel?
            if not channel:
                return (SHOW_MESSAGE, "Usage: /part <channel>")
            self.irc_core.part_channel(channel)
            return None

        @self.add_command('/nick')
        def nick(new_nick):
            if not new_nick:
                return (SHOW_MESSAGE, "Usage: /nick <new_nick>")
            self.irc_core.change_nick(new_nick)
            return None

        @self.add_command('/msg')
        def msg(params):
            try:
                nick, message = params.split(None, 1)
            except ValueError:
                return (SHOW_MESSAGE, "Usage: /msg <nick> <message>")

            self.irc_core.send_privmsg(nick, message)
            return None

        @self.add_command('/ns')
        @self.add_command('/nickserv')
        def msg_nickserv(message):
            return msg('NickServ ' + message)

        @self.add_command('/ms')
        @self.add_command('/memoserv')
        def msg_memoserv(message):
            return msg('MemoServ ' + message)

        # TODO: /me, /kick, /ban etc... lots of commands to add

    def handle_command(self, current_channel_or_nick, message):
        """This runs when the user types something.

        This takes care of special commands like ``/join #somechannel``
        as well as sending messages to the channel.

        The current_channel_or_nick can be:
            * a nickname that the user is talking with using PMs
            * a channel name
            * None if the user is not looking at a channel right now
        """
        if not message:
            return None

        # '//lol' escapes the /, but '//lol/' is a literal '/lol/'
        if message.startswith('/') and not message.startswith('//'):
            # we have a special command
            try:
                command, args = message.split(None, 1)
            except ValueError:
                command = message.strip()
                args = ''

            if command in self._commands:
                return self._commands[command](args)
            return (SHOW_MESSAGE, "There's no '%s' command :(" % command)

        # not a special command
        if current_channel_or_nick is None:
            return (SHOW_MESSAGE,
                    "You can't send messages directly to the server. "
                    "Join a channel instead and send messages there.")

        if message.startswith('//'):
            message = message.replace('//', '/', 1)
        self.irc_core.send_privmsg(current_channel_or_nick, message)
        return None
