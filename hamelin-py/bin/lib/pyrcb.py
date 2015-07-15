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
from collections import defaultdict
from multiprocessing.pool import ThreadPool
import errno
import re
import socket
import ssl
import threading
import time

__version__ = "1.5.1"


class IrcBot(object):
    def __init__(self, debug_print=False, print_function=print, delay=True):
        self.debug_print = debug_print
        self.print_function = print_function
        self.delay = delay

    # Initializes instance variables.
    def _init(self):
        self.thread_pool = ThreadPool(processes=16)
        self.listen_thread = None

        self._delay_event = threading.Event()
        self._messages = []
        self.last_message = defaultdict(lambda: (0, 0))
        # Format:
        #   self._messages[number] = (time, text)
        #   self.last_message[target] = (time, consecutive)

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
        self._init()
        self.hostname = hostname
        self.port = port
        if use_ssl:
            reqs = ssl.CERT_REQUIRED if ca_certs else ssl.CERT_NONE
            self.socket = ssl.wrap_socket(
                self.socket, cert_reqs=reqs, ca_certs=ca_certs)

        self.socket.connect((hostname, port))
        self.alive = True
        if self.delay:
            t = threading.Thread(target=self._delay_loop)
            t.daemon = True
            t.start()

    def password(self, password):
        self._writeline("PASS :{0}".format(password))

    def register(self, nickname):
        self.nickname = nickname
        self._writeline("USER {0} 8 * :{0}".format(nickname))
        self._writeline("NICK {0}".format(nickname))
        while not self.is_registered:
            line = self._readline()
            if line is None:
                return
            if self._parse(line)[1] == "433":  # ERR_NICKNAMEINUSE
                raise ValueError("Nickname is already in use")
            self._handle(line)

    def join(self, channel):
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
        except socket.error as e:
            if e.errno != errno.EPIPE:
                raise
        self._close_socket()
        self.alive = False

    def nick(self, new_nickname):
        self._writeline("NICK {0}".format(new_nickname))

    def names(self, channel):
        if not channel.isspace():
            self._writeline("NAMES {0}".format(channel))

    def send(self, target, message):
        self._add_delayed(target, "PRIVMSG {0} :{1}".format(target, message))

    def send_notice(self, target, message):
        self._add_delayed(target, "NOTICE {0} :{1}".format(target, message))

    def send_raw(self, message):
        self._writeline(message)

    def on_join(self, nickname, channel, is_self):
        pass

    def on_part(self, nickname, channel, message):
        pass

    def on_quit(self, nickname, message):
        pass

    def on_kick(self, nickname, channel, target, is_self):
        pass

    def on_nick(self, nickname, new_nickname, is_self):
        pass

    def on_names(self, channel, names):
        pass

    def on_message(self, message, nickname, target, is_query):
        pass

    def on_notice(self, message, nickname, target, is_query):
        pass

    def on_other(self, nickname, command, args):
        pass

    def listen(self, async_events=False):
        while True:
            try:
                line = self._readline()
            except socket.error as e:
                if e.errno == errno.EPIPE:
                    self._close_socket()
                    return
                raise
            if line is None:
                self._close_socket()
                return
            else:
                self._handle(line)

    def listen_async(self, callback=None, async_events=False):
        def target():
            self.listen(async_events)
            if callback:
                callback()
        self.listen_thread = threading.Thread(target=target)
        self.listen_thread.daemon = True
        self.listen_thread.start()

    def wait(self):
        if self.listen_thread:
            self.listen_thread.join()

    def is_alive(self):
        return self.alive

    # Parses an IRC message and calls the appropriate event,
    # starting it on a new thread if requested.
    def _handle(self, message, async_events=False):
        def async(target, *args):
            if async_events:
                self.thread_pool.apply_async(target, args)
            else:
                target(*args)

        nick, cmd, args = self._parse(message)
        is_self = (nick or "").lower() == self.nickname.lower()

        if cmd == "PING":
            self._writeline("PONG :{0}".format(args[0]))
        elif cmd == "MODE":
            self.is_registered = True
        elif cmd == "JOIN":
            if is_self:
                self.channels.append(args[0])
            async(self.on_join, nick, args[0], is_self)
        elif cmd == "PART":
            async(self.on_part, nick, args[0], (args[1:] or [""])[0])
        elif cmd == "QUIT":
            async(self.on_quit, nick, (args or [""])[0])
        elif cmd == "KICK":
            is_self = args[1].lower() == self.nickname.lower()
            async(self.on_kick, nick, args[0], args[1], is_self)
        elif cmd == "NICK":
            if is_self:
                self.nickname = args[0]
            async(self.on_nick, nick, args[0], is_self)
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

    # Parses an IRC message.
    def _parse(self, message):
        # Regex to parse IRC messages
        match = re.match(r"(?::([^!@ ]+)[^ ]* )?([^ ]+)"
                         r"((?: [^: ][^ ]*){0,14})(?: :?(.+))?",
                         message)

        nick, cmd, args, trailing = match.groups()
        args = (args or "").split()
        if trailing:
            args.append(trailing)
        return (nick, cmd, args)

    # Adds a delayed message, or sends the message if delays are off.
    def _add_delayed(self, target, message):
        if not self.delay:
            self._writeline(message)
            return

        last_time, consecutive = self.last_message[target]
        last_delta = time.time() - last_time
        if last_delta >= 5:
            consecutive = 0

        delay = min(consecutive / 10, 1.5)
        message_time = max(last_time, time.time()) + delay
        self.last_message[target] = (message_time, consecutive + 1)

        self._messages.append((message_time, message))
        self._delay_event.set()

    # Sends delayed messages at the appropriate time.
    def _delay_loop(self):
        while self.alive:
            self._delay_event.clear()
            if any(self._messages):
                # Get message with the lowest time.
                message_time, message = min(self._messages)
                delay = message_time - time.time()

                # If there is no delay or the program finishes
                # waiting for the delay, send the message.
                if delay <= 0 or not self._delay_event.wait(timeout=delay):
                    self._writeline(message)
                    self._messages.remove((message_time, message))
            else:
                self._delay_event.wait()

    # Reads a line from the socket.
    def _readline(self):
        while "\r\n" not in self._buffer:
            data = self.socket.recv(1024)
            if len(data) == 0:
                return
            self._buffer += data.decode("utf8", "ignore")

        line, self._buffer = self._buffer.split("\r\n", 1)
        if self.debug_print:
            self.print_function(line)
        return line

    # Writes a line to the socket.
    def _writeline(self, data):
        self.socket.sendall((data + "\r\n").encode("utf8", "ignore"))
        if self.debug_print:
            self.print_function(">>> " + data)

    # Closes the socket.
    def _close_socket(self):
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()
        except socket.error as e:
            if e.errno != errno.EPIPE:
                raise
        self.alive = False
        self._delay_event.set()
