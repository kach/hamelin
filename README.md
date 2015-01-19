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

`hamelin.py`, included with this file, is a reference implementation of a
`hamelin`-compliant daemon. It is the Py'd Piper.

## Specification v. 0.1

`hamelin.py` follows the following specification. Alternative implementations
are encouraged as long as they abide by the specification outlined below.

The `hamelin` command runs a **daemon** process. The daemon should run
continuously on the host machine.

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
This is line-buffered.

Content in `stderr` is forwarded to the daemon's own `stderr` for debugging
purposes.

The server process runs until either it exits or the client closes the
connection (this event is obviously defined differently for each connection
type). If the client closes the connection, the server is sent `SIGTERM`. If
the server exits, the client connection is closed in an unspecified manner. If
the server exits with a non-zero exit code, `hamelin` logs this to its
`stderr`.

A `hamelin` daemon sets certain environment variables for the subprocess, which
provide metadata about the connection and setup. These are outlined in the
table below:

| Variable    | Meaning |
| --------    | ------- |
| `H-VERSION` | The name and version of the `hamelin` daemon running.
| `H-TYPE`    | The name and version of the connection type, for example, `IRC-0.2` |
| `H-OPTIONS` | These would correspond to the command-line options (for a web server, you would get the host and port, for example). |
| `H-CLIENT`  | Information about client. The content here depends on `H-TYPE`. For a web browser, it might be the user-agent string. For IRC, it could be the server/nick/channel. |

All of these are optional.

Additional environment variables are set depending on the daemon type. All
`hamelin` environment variables are prefixed with `H-`.

Finally, the daemon should pass along user-specified command-line arguments to
the server *unchanged*. This provides the user with a means to modify the
behavior of a server script without editing it.
