# based on a thing that myst wrote for me
# thanks myst :)   https://github.com/PurpleMyst/
import collections
import enum
import queue
import socket
import threading


_Message = collections.namedtuple(
    "_Message", ["sender", "sender_is_server", "command", "args"])

# from rfc1459
RPL_ENDOFMOTD = '376'
RPL_NAMREPLY = '353'
RPL_ENDOFNAMES = '366'


class IrcEvent(enum.Enum):
    # The comments above each enum value represent the parameters they should
    # come with.

    # (channel, nicklist)
    self_joined = enum.auto()

    # (old_nick, new_nick)
    # IrcCore.nick is updated before this event is generated
    self_changed_nick = enum.auto()

    # (channel)
    self_parted = enum.auto()

    # ()
    self_quit = enum.auto()

    # (sender_nick, channel)
    user_joined = enum.auto()

    # (old_nick, new_nick)
    user_changed_nick = enum.auto()

    # (sender_nick, channel, reason)
    # reason can be None
    user_parted = enum.auto()

    # (sender_nick, reason)
    # reason can be None
    user_quit = enum.auto()

    # (recipient, text)
    sent_privmsg = enum.auto()

    # (sender_nick_or_channel, recipient, text)
    received_privmsg = enum.auto()

    # (sender_server, command, args)
    server_message = enum.auto()

    # (sender_nick, command, args)
    # if you want to handle some of these, add the code to this file
    # not so that this creates an unknown_message that is parsed elsewhere
    # currently AT LEAST these things cause unknown messages:
    #    * KICK
    #    * MODE (ban, op, voice etc)
    #    * INVITE
    unknown_message = enum.auto()


class _IrcInternalEvent(enum.Enum):
    got_message = enum.auto()

    should_join = enum.auto()
    should_part = enum.auto()
    should_quit = enum.auto()
    should_send_privmsg = enum.auto()
    should_change_nick = enum.auto()


class IrcCore:
    def __init__(self, host, port, nick):
        self.host = host
        self.port = port
        self._running = True
        self.nick = nick

        self._sock = socket.socket()
        self._linebuffer = collections.deque()

        self._internal_queue = queue.Queue()
        self.event_queue = queue.Queue()

        # TODO: is automagic RPL_NAMREPLY in an rfc??
        # TODO: what do the rfc's say about huge NAMES replies?
        #
        # servers seem to send RPL_NAMREPLY followed by RPL_ENDOFNAMES when a
        # client connects
        # the replies are collected here before emitting a self_joined event
        self._names_replys = {}   # {channel: [nick1, nick2, ...]}

    def _send(self, *parts):
        data = " ".join(parts).encode("utf-8") + b"\r\n"
        self._sock.sendall(data)

    def _recv_line(self):
        if not self._linebuffer:
            data = bytearray()

            # this accepts both \r\n and \n because b'blah blah\r\n' ends
            # with b'\n'
            while not data.endswith(b"\n"):
                chunk = self._sock.recv(4096)
                if chunk:
                    data += chunk
                else:
                    raise RuntimeError("Server closed the connection!")

            lines = data.decode("utf-8", errors='replace').splitlines()
            self._linebuffer.extend(lines)

        return self._linebuffer.popleft()

    def _add_messages_to_internal_queue(self):
        # We need to have this function because it would be very complicated to
        # wait on two different queues, one for requests to send stuff and one
        # received messages.
        while self._running:
            line = self._recv_line()
            if not line:
                # i'm not sure when this runs, but it runs sometimes
                continue
            if line.startswith("PING"):
                self._send(line.replace("PING", "PONG", 1))
                continue
            self._internal_queue.put((_IrcInternalEvent.got_message,
                                      self._split_line(line)))

    @staticmethod
    def _split_line(line):
        if line.startswith(":"):
            sender, command, *args = line.split(" ")
            sender = sender[1:]
            if "!" in sender:
                # use user_and_host.split('@', 1) to separate user and host
                # TODO: include more stuff about the user than the nick?
                sender, user_and_host = sender.split("!", 1)
                sender_is_server = False
            else:
                # leave sender as is
                sender_is_server = True
        else:
            sender_is_server = True   # TODO: when does this code run?
            sender = None
            command, *args = line.split(" ")
        for n, arg in enumerate(args):
            if arg.startswith(":"):
                temp = args[:n]
                temp.append(" ".join(args[n:])[1:])
                args = temp
                break
        return _Message(sender, sender_is_server, command, args)

    def _mainloop(self):
        while self._running:
            event, *args = self._internal_queue.get()

            if event == _IrcInternalEvent.got_message:
                [msg] = args
                if msg.command == "PRIVMSG":
                    recipient, text = msg.args
                    self.event_queue.put((IrcEvent.received_privmsg,
                                          msg.sender, recipient, text))

                elif msg.command == "JOIN":
                    [channel] = msg.args
                    if msg.sender == self.nick:
                        # there are plenty of comments in other
                        # _names_replys code
                        self._names_replys[channel] = []
                    else:
                        self.event_queue.put((IrcEvent.user_joined,
                                              msg.sender, channel))

                elif msg.command == "PART":
                    channel = msg.args[0]
                    reason = msg.args[1] if len(msg.args) >= 2 else None
                    if msg.sender == self.nick:
                        self.event_queue.put((IrcEvent.self_parted, channel))
                    else:
                        self.event_queue.put((IrcEvent.user_parted,
                                              msg.sender, channel, reason))

                elif msg.command == "NICK":
                    old = msg.sender
                    [new] = msg.args
                    if old == self.nick:
                        self.nick = new
                        self.event_queue.put((IrcEvent.self_changed_nick,
                                              old, new))
                    else:
                        self.event_queue.put((IrcEvent.user_changed_nick,
                                              old, new))

                elif msg.command == "QUIT":
                    reason = msg.args[0] if msg.args else None
                    if msg.sender == self.nick:
                        self.event_queue.put((IrcEvent.self_quit,))
                        self._running = False
                    else:
                        self.event_queue.put((IrcEvent.user_quit,
                                              msg.sender, reason))

                elif msg.sender_is_server:
                    if msg.command == RPL_NAMREPLY:
                        # TODO: wtf are the first 2 args?
                        # rfc1459 doesn't mention them, but freenode
                        # gives 4-element msg.args lists
                        channel, names = msg.args[-2:]

                        # TODO: don't ignore @ and + prefixes
                        self._names_replys[channel].extend(
                            name.lstrip('@+') for name in names.split())

                    elif msg.command == RPL_ENDOFNAMES:
                        # joining a channel finished
                        channel, human_readable_message = msg.args[-2:]
                        nicks = self._names_replys.pop(channel)
                        self.event_queue.put((IrcEvent.self_joined,
                                              channel, nicks))

                    else:
                        self.event_queue.put((
                            IrcEvent.server_message,
                            msg.sender, msg.command, msg.args))

                else:
                    self.event_queue.put((IrcEvent.unknown_message,
                                          msg.sender, msg.command, msg.args))

            elif event == _IrcInternalEvent.should_join:
                [channel] = args
                self._send("JOIN", channel)

            elif event == _IrcInternalEvent.should_part:
                channel, reason = args
                if reason is None:
                    self._send("PART", channel)
                else:
                    # FIXME: the reason thing doesn't seem to work
                    self._send("PART", channel, ":" + reason)

            elif event == _IrcInternalEvent.should_quit:
                assert not args
                self._send("QUIT")
                self._running = False

            elif event == _IrcInternalEvent.should_send_privmsg:
                recipient, text = args
                self._send("PRIVMSG", recipient, ":" + text)
                self.event_queue.put((IrcEvent.sent_privmsg, recipient, text))

            elif event == _IrcInternalEvent.should_change_nick:
                [new_nick] = args
                self._send("NICK", new_nick)

            else:
                raise RuntimeError("Unrecognized internal event!")

            self._internal_queue.task_done()

        self.event_queue.put((IrcEvent.self_quit,))

    # if an exception occurs while connecting, it's raised right away
    # run this in a thread if you don't want blocking
    # this starts the main loop
    def connect(self):
        self._sock.connect((self.host, self.port))
        self._send("NICK", self.nick)
        # TODO: allow specifying different nick and realname
        self._send("USER", self.nick, "0", "*", ":" + self.nick)

        threading.Thread(target=self._add_messages_to_internal_queue).start()
        threading.Thread(target=self._mainloop).start()

    def join_channel(self, channel):
        self._internal_queue.put((_IrcInternalEvent.should_join, channel))

    def part_channel(self, channel, reason=None):
        self._internal_queue.put((_IrcInternalEvent.should_part,
                                  channel, reason))

    def send_privmsg(self, nick_or_channel, text):
        self._internal_queue.put((_IrcInternalEvent.should_send_privmsg,
                                  nick_or_channel, text))

    # this doesn't change self.nick right away, but .nick is updated
    # when the nick name has actually changed
    # emits a self_changed_nick event on success
    def change_nick(self, new_nick):
        self._internal_queue.put((_IrcInternalEvent.should_change_nick,
                                  new_nick))

    # part all channels before calling this
    def quit(self):
        self._internal_queue.put((_IrcInternalEvent.should_quit,))


if __name__ == '__main__':
    core = IrcCore('chat.freenode.net', 6667, 'testieeeeeeeeeee')
    core.connect()
    while True:
        event = core.event_queue.get()
        print(event)
        if event[0] == IrcEvent.self_quit:
            break
        if event[0] == IrcEvent.received_privmsg and event[-1] == 'asd':
            core.part_channel('##testingggggg', 'bye')
            core.quit()
        if event[0] == IrcEvent.server_message:
            server, command, args = event[1:]
            if command == RPL_ENDOFMOTD:
                core.join_channel('##testingggggg')
