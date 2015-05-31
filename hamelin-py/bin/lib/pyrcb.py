# Copyright (C) 2015 nickolas360 (https://github.com/nickolas360)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function
from multiprocessing.pool import ThreadPool
import re
import socket
import ssl
import threading

__version__ = "1.2.0"


class IrcBot(object):
    def __init__(self, debug_print=False, print_function=print):
        self.debug_print = debug_print
        self.print_function = print_function
        self.thread_pool = ThreadPool(processes=16)

        self._buffer = ""
        self.socket = socket.socket()
        self.hostname = None
        self.port = None

        self._names = []
        self.channels = []
        self.alive = False
        self.is_registered = False
        self.nickname = None

    def connect(self, hostname, port, use_ssl=False, ca_certs=None):
        self._cleanup()
        self.hostname = hostname
        self.port = port
        if use_ssl:
            reqs = ssl.CERT_REQUIRED if ca_certs else ssl.CERT_NONE
            self.socket = ssl.wrap_socket(
                self.socket, cert_reqs=reqs, ca_certs=ca_certs)
        self.socket.connect((hostname, port))
        self.alive = True

    def register(self, nickname):
        self.nickname = nickname
        self._writeline("USER {0} 8 * :{0}".format(nickname))
        self._writeline("NICK {0}".format(nickname))
        while not self.is_registered:
            line = self._readline()
            if line is None:
                return
            self._handle(line)

    def join(self, channel):
        self.channels.append(channel.lower())
        self._writeline("JOIN {0}".format(channel))

    def part(self, channel, message=None):
        if channel.lower() in self.channels:
            part_msg = " :" + message if message else ""
            self._writeline("PART {0}{1}".format(channel, part_msg))
            self.channels.remove(channel.lower())

    def quit(self, message=None):
        try:
            quit_msg = " :" + message if message else ""
            self._writeline("QUIT{0}".format(quit_msg))
            self.socket.shutdown(socket.SHUT_RDWR)
        except socket.error:
            pass
        self.socket.close()
        self.alive = False

    def names(self, channel):
        if not channel.isspace():
            self._writeline("NAMES {0}".format(channel))

    def send(self, target, message):
        self._writeline("PRIVMSG {0} :{1}".format(target, message))

    def send_notice(self, target, message):
        self._writeline("NOTICE {0} :{1}".format(target, message))

    def send_raw(self, message):
        self._writeline(message)

    def listen(self, async_events=False):
        while True:
            try:
                line = self._readline()
            except socket.error:
                self.quit()
                return
            if line is None:
                return
            else:
                self._handle(line)

    def listen_async(self, callback=None, async_events=False):
        def target():
            self.listen(async_events)
            if callback:
                callback()
        t = threading.Thread(target=target)
        t.daemon = True
        t.start()

    def is_alive(self):
        return self.alive

    def on_join(self, nickname, channel):
        # To be overridden
        pass

    def on_part(self, nickname, channel, message):
        # To be overridden
        pass

    def on_quit(self, nickname, message):
        # To be overridden
        pass

    def on_kick(self, nickname, channel, target, is_self):
        # To be overridden
        pass

    def on_names(self, channel, names):
        # To be overridden
        pass

    def on_message(self, message, nickname, target, is_query):
        # To be overridden
        pass

    def on_notice(self, message, nickname, target, is_query):
        # To be overridden
        pass

    def on_other(self, nickname, command, args):
        # To be overridden
        pass

    def _handle(self, message, async_events=False):
        def async(target, *args):
            if async_events:
                self.thread_pool.apply_async(target, args)
            else:
                target(*args)

        nick, cmd, args = self._parse(message)
        if cmd == "PING":
            self._writeline("PONG :{0}".format(args[0]))
        elif cmd == "MODE":
            self.is_registered = True
        elif cmd == "JOIN":
            async(self.on_join, nick, args[0])
        elif cmd == "PART":
            async(self.on_part, nick, args[0], args[1])
        elif cmd == "QUIT":
            async(self.on_quit, nick, args[0])
        elif cmd == "KICK":
            is_self = args[1].lower() == self.nickname.lower()
            async(self.on_kick, nick, args[0], args[1], is_self)
        elif cmd == "433":  # ERR_NICKNAMEINUSE
            raise ValueError("Nickname is already in use")
        elif cmd == "353":  # RPL_NAMREPLY
            names = args[-1].replace("@", "").replace("+", "").split()
            self._names.append((args[-2], names))
        elif cmd == "366":  # RPL_ENDOFNAMES
            for channel, names in self._names:
                async(self.on_names, channel, names)
            if not self._names:
                async(self.on_names, None, None)
            self._names = []
        elif cmd == "PRIVMSG" or cmd == "NOTICE":
            is_query = args[0].lower() == self.nickname.lower()
            target = nick if is_query else args[0]
            event = self.on_message if cmd == "PRIVMSG" else self.on_notice
            async(event, args[-1], nick, target, is_query)
        else:
            async(self.on_other, nick, cmd, args)

    def _parse(self, message):
        match = re.match(r"(?::([^!@ ]+)[^ ]* )?([^ ]+)"
                         r"((?: [^: ][^ ]*){0,14})(?: :?(.+))?",
                         message)

        nick, cmd, args, trailing = match.groups()
        args = (args or "").split()
        if trailing:
            args.append(trailing)
        return (nick, cmd, args)

    def _readline(self):
        while "\r\n" not in self._buffer:
            data = self.socket.recv(1024)
            if len(data) == 0:
                self._cleanup()
                return
            self._buffer += data.decode("utf8", "ignore")

        line, self._buffer = self._buffer.split("\r\n", 1)
        if self.debug_print:
            self.print_function(line)
        return line

    def _writeline(self, data):
        self.socket.sendall((data + "\r\n").encode("utf8", "ignore"))
        if self.debug_print:
            self.print_function(">>> " + data)

    def _cleanup(self):
        self._buffer = ""
        self.is_registered = False
        self.channels = []
