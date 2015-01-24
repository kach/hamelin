Hamelin
=======

`hamelin` is a specification to create multiple interfaces for simple scripts.
`hamelin` negotiates I/O details so that all you need to manage is your
scripts' logic. Think of it as a general-purpose, modern-day CGI that isn't
restricted to HTTP. Or think of it is a way to make *everything* a filter.

As a simple example, here's the `net` plugin in action:

    $ python hamelin/net.py localhost 8080 grep --line-buffered "filter" &
    $ cat /usr/share/dict/words | nc localhost 8080
    filter
    filterability
    filterable
    filterableness
    filterer
    filtering
    filterman
    infilter
    nonultrafilterable
    prefilter
    refilter
    ultrafilter
    ultrafilterability
    ultrafilterable
    unfiltered

Or, here's a simple quoteDB/guestbook app written in 8 lines of code:
```python
import fileinput
import sys
print "Type your quote below. Hit ^D when done."
sys.stdout.flush()
f = open("/home/***/public_html/qdb.txt", "a")
f.write("\n~~~~~~~\n\n")
for line in fileinput.input():
    f.write(line)
    f.close()
```

    hamelin-net localhost 8080 /usr/bin/python guestbook.py

`hamelin-py`, included with this repository, is a reference implementation of a
`hamelin`-compliant daemon module. `net.py` implements a TCP socket-based
daemon. For now, these can be installed with Python (see
`/hamelin-py/README.md` for instructions), but a `hamelin` plugin manager is in
the works.

## Specification v. 0.1 (unstable)

`hamelin.py` follows the following specification. Alternative implementations
are encouraged as long as they abide by the specification outlined below.

Phrases such as SHOULD, MUST, etc. are as per RFC 2119.

The `hamelin` command runs a **daemon** process. The daemon runs continuously
on the host machine.

The daemon instantiates a new subprocess running your script for *every*
"connection". This process is called a **server**. A connection could be any
form of input/output. Some possible examples are:

- A user on a teletype
- A telnet or plain socket server
- An IRC bot
- A RESTful HTTP API
- A WebSocket server

Each connection is called a *client*.

The daemon sends client data to the server's standard input (`stdin`). In
addition, the server's standard output (`stdout`) is sent back to the client.
All data MUST be line-buffered. The daemon MAY modify data to make it more
suitable for a server, but it MUST clearly document these changes.

Content in `stderr` MUST be forwarded to the daemon's own `stderr` for
debugging purposes. This content MUST NOT be modified when sent to `stderr`,
but it MAY be intercepted and used for purposes such as informing the client of
errors.

The server process runs until either it exits or the client closes the
connection (this event is obviously defined differently for each connection
type). If the client closes the connection, the server MUST be sent `SIGTERM`.
Note that sending `SIGTERM` is no guarantee of terminating a process. If the
server exits, the client connection is closed in an unspecified manner.  If the
server exits with a status code that is not `0` or `SIGTERM`, the daemon SHOULD
log this to `stderr`.

A `hamelin` daemon SHOULD set certain environment variables for the subprocess,
to provide metadata about the connection and setup. These are outlined in the
table below:

| Variable    | Meaning |
| --------    | ------- |
| `H-VERSION` | The name and version of the `hamelin` daemon running.
| `H-TYPE`    | The name and version of the connection type, for example, `IRC-0.2-INSECURE` |
| `H-CLIENT`  | Information about client. The content here depends on `H-TYPE`. For a web browser, it might be the user-agent string. For IRC, it could be the server/nick/channel. |

Additional environment variables MAY be set depending on the daemon type. All
`hamelin` environment variables MUST BE prefixed with `H-`.

Finally, the daemon MUST pass along user-specified command-line arguments to
the server *unchanged*, to provide the user with a means to modify the behavior
of a server script without editing it.
