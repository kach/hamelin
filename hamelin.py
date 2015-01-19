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
    def __init__(self, args):
        self.args = args
    def run(self):
        pass # override me!
    def create_server(self, env=None):
        newenv = {}
        if env is not None:
            newenv = env
        oldenv = os.environ.copy()
        for (key, value) in oldenv.iteritems():
            newenv[key] = value
        return server(self, newenv)

class server:
    def __init__(self, daemon, env):
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
    def event_loop(self):
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
                    print "Reading!"
                    readable[0].flush()
                    line = readable[0].readline()
                    print "Got", line[:-1]
                    if len(line) == 0:
                        self.stdout_open = False
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
        print text # override me!
    def handle_error(self, text):
        sys.stderr.write(text) # probably override me!
    def handle_quit(self, code):
        pass # override me!
    
    # Methods
    def send(self, text):
        if not self.stdin_open:
            raise Exception("Tried to talk after sending EOF!")
        else:
            self.write_queue.put(text)
    def kill(self):
        if self.alive:
            self.will_die = True
        else:
            raise Exception("Tried to kill dead process.")
    def eof(self):
        self.stdin_open = False 
