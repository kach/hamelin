#!/usr/bin/env python

import subprocess
import select
import signal
import os
import sys
import threading
import Queue
import time

""" The Py'd Piper of Hamelin """

class daemon:
    """ This is a template class to create a daemon. """
    def __init__(self, args):
        """ Create a new daemon which runs `args` as a server. You should not
            override this method. Run-time options should be configured as
            arguments to `run`.
        """
        self.args = args
    def run(self):
        """ Override this method to start a new daemon process. """
        pass
    def create_server(self, env=None):
        """ Returns a new `hamelin.server` object bound to this daemon. The
            optional argument `env` is a dictionary that allows you to set
            environment variables that are *appended* to the environment the
            daemon runs in.
        """
        newenv = {}
        if env is not None:
            newenv = env
        oldenv = os.environ.copy()
        for (key, value) in oldenv.iteritems():
            newenv[key] = value
        return server(self, newenv)

class server:
    """ This is is a server process---it handles the process generated for
        one connection.
        
        To listen for events, *assign* to `handle_data`, `handle_error`, and
        `handle_quit` before running `startup`.

        `hamelin.server` objects are *not* reusable. You can monitor its status
        with the boolean attribute `alive`. If `alive` is False, the server is
        either not yet listening or has exited.
    """
    def __init__(self, daemon, env):
        """ Initializes a new server bound to a daemon and runing in an
            environment. """
        self.daemon = daemon
        self.env = env
        self.alive = False
        self.will_die = False
        self.stdin_open = True
        self.stdout_open = True
        self.process = None
        self.thread  = None
        self.write_queue = Queue.Queue()

    def startup(self):
        """ Open the subprocess and start a thread to monitor its I/O. """
        if not self.alive:
            self.process = subprocess.Popen(
                self.daemon.args,
                shell  = False,
                stdin  = subprocess.PIPE,
                stdout = subprocess.PIPE,
                stderr = subprocess.PIPE,
                env    = self.env
            )
            self.alive = True
            self.thread = threading.Thread(
                target = self.event_loop,
                name   = "server-thread-[%s]"%(self.daemon.args[0])
            )
            self.thread.start()
        else:
            raise Exception("Tried to startup a live process.")
    def event_loop(self):
        """ This loop runs in a separate thread to provide safe,
            semi-asynchronous I/O operations. """
        while self.alive:
            time.sleep(0) # yield thread
            poll = self.process.poll()
            if poll is not None and not self.stdout_open:
                self.alive = False
                self.handle_quit(poll)
            elif self.will_die  and not self.stdout_open:
                self.alive = False
                self.process.terminate()
                while self.process.poll() is None:
                    pass
                self.handle_quit(self.process.poll())
            else:
                if not self.stdin_open and not self.process.stdin.closed:
                    self.process.stdin.close()


                readable, writable, errors = select.select(
                    [self.process.stdout],
                    [self.process.stdin] if not self.process.stdin.closed else [],
                    [self.process.stderr],
                    1
                )
                if len(readable) > 0 and self.stdout_open:
                    readable[0].flush()
                    line = readable[0].readline()
                    if line:
                        print "Recieved from process: '{0}'".format(line[:-1])
                    if len(line) == 0:
                        self.stdout_open = False
                        continue
                    self.handle_data(line)
                if len(writable) > 0:
                    while not self.write_queue.empty():
                        text = self.write_queue.get()
                        writable[0].write(text)
                        writable[0].flush()
                        self.write_queue.task_done()
                if len(errors) > 0:
                    self.handle_error(errors[0].readline())
    
    # Events
    def handle_data(self, text):
        """ Called when the server prints to stdout. """
        print text # override me!
    def handle_error(self, text):
        """ Called when the server prints to stderr, defaults to forwarding to
            the daemon's stderr. """
        sys.stderr.write(text) # probably override me!
    def handle_quit(self, code):
        """ Called when the server exits, with the exit code. """
        pass # override me!
    
    # Methods
    def send(self, text):
        """ Send text to the server's stdin. """
        if not self.stdin_open:
            raise Exception("Tried to talk after sending EOF!")
        else:
            self.write_queue.put(text)
    def kill(self):
        """ Send the server `SIGTERM`. """
        if self.alive:
            self.will_die = True
        else:
            raise Exception("Tried to kill dead process.")
    def eof(self):
        """ Send the server `EOF`. """
        self.stdin_open = False 

if __name__ == '__main__':
    print "hamelin.py itself doesn't do anything exciting!"
