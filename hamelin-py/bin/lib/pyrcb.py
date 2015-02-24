# Copyright (C) 2015 nickolas360 (https://github.com/nickolas360)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function
import socket


class IrcBot(object):
    def __init__(self, debug_print=False):
        self._buffer = ""
        self.socket = socket.socket()
        self.hostname = None
        self.port = None

        self.debug_print = debug_print
        self.is_registered = False
        self.nickname = None
        self.channels = []

    def connect(self, hostname, port):
        self.hostname = hostname
        self.port = port
        self.socket.connect((hostname, port))

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

    def part(self, channel):
        if channel.lower() in self.channels:
            self._writeline("PART {0}".format(channel))
            self.channels.remove(channel.lower())

    def quit(self):
        self._writeline("QUIT")
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()

    def send(self, target, message):
        self._writeline("PRIVMSG {0} :{1}".format(target, message))

    def listen(self):
        while True:
            line = self._readline()
            if line is None:
                return
            self._handle(line)

    def on_join(self, nickname, channel):
        # To be overridden
        pass

    def on_part(self, nickname, channel):
        # To be overridden
        pass

    def on_quit(self, nickname):
        # To be overridden
        pass

    def on_message(self, message, nickname, target, is_query):
        # To be overridden
        pass

    def _handle(self, message):
        split = message.split(" ", 3)
        if len(split) < 2:
            return
        if split[0].upper() == "PING":
            self._writeline("PONG {0}".format(split[1]))
            return
        
        nickname = split[0].split("!")[0].split("@")[0][1:]
        command = split[1].upper()
        if command == "MODE":
            self.is_registered = True
        elif command == "JOIN":
            self.on_join(nickname, split[2])
        elif command == "PART":
            self.on_part(nickname, split[2])
        elif command == "QUIT":
            self.on_quit(nickname)
        elif command == "PRIVMSG":
            is_query = split[2] == self.nickname
            target = nickname if is_query else split[2]
            self.on_message(split[3][1:], nickname, target, is_query)

    def _readline(self):
        while "\r\n" not in self._buffer:
            data = self.socket.recv(1024)
            if len(data) == 0:
                self._cleanup()
                return
            self._buffer += data.decode("utf8")

        line, self._buffer = self._buffer.split("\r\n", 1)
        if self.debug_print:
            print(line)
        return line

    def _writeline(self, data):
        self.socket.sendall((data + "\r\n").encode("utf8"))
        if self.debug_print:
            print(">>> " + data)

    def _cleanup(self):
        self._buffer = ""
        self.registered = False
        self.channels = []
