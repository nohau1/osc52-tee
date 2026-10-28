# Security

`osc52-tee` is a small local tool that parses terminal output and writes the
result to your clipboard and/or files. This document describes what it can and
cannot do, and which risks are yours to manage.

## Trust model

The tool is designed for **your machine talking to servers you trust**. It does
not add authentication, encryption or sandboxing; it relies on SSH for transport
security.

- **Local machine**: trusted. It owns the clipboard and runs the clipboard
  command.
- **Remote host**: trusted to the same degree as when you run any terminal app
  there. A compromised remote can already send arbitrary terminal escape
  sequences; OSC 52 is just one of them.
- **Clipboard command** (`wl-copy`, `xclip`, `pbcopy`, ...): trusted local
  software, resolved via `PATH`.

## What a remote host can do

With or without this wrapper, a program that can write to your terminal can
emit OSC 52. If your terminal or this wrapper honours it, the remote can:

- **Overwrite your local clipboard** with arbitrary text. This is the main risk:
  a malicious remote could put a command in your clipboard and wait for you to
  paste it into a shell.
- **Spam copies** to churn the clipboard and consume CPU. `osc52-tee` mitigates
  this with a bounded queue (16 pending copies), one worker process at a time,
  a 10-second timeout per clipboard command, and a maximum payload size
  (1 MiB by default, `--max-bytes`).
- **Send other escape sequences** (titles, hyperlinks, colors, ...). That is a
  property of terminals, not of this tool.

A remote host **cannot** use this tool to read your clipboard:

- OSC 52 read queries (`ESC ] 52 ; c ; ? ST`) are ignored by the parser.
- The clipboard command only receives data on stdin; its stdout/stderr are
  discarded.
- There is no network listener and no RPC surface.

If you do not trust a host, do not run `ossh`/`osc52-tee` against it (and
consider disabling OSC 52 in your terminal as well).

## Clipboard data at rest

The `--log` and `--stream` files contain everything you copy: API keys,
passwords, tokens, private messages. This is often exactly the data you do not
want on disk.

- Files are created with mode `0600` and are only readable by your user.
- They still end up in backups, snapshots, synced home directories and crash
  dumps, and `root` can read them.
- `ossh` and the recommended SSH workflow use `--no-log --no-stream`, so
  nothing is written to disk.
- The server-side variant (`occlip` + `tail -f`) stores copies on the **remote**
  host. Its administrators/root can read them, and the log outlives your
  session. Prefer the local-clipboard workflow for sensitive data.
- Base64 in `clipboard.b64` is encoding, **not encryption**.

Clear the logs when you no longer need them:

```sh
: > ~/.local/share/osc52-tee/clipboard.log
: > ~/.local/share/osc52-tee/clipboard.b64
```

## Command execution

`--copy-command` / `OSC52_TEE_COPY_COMMAND` is local configuration. It is parsed
with `shlex.split` and executed directly, **without a shell**, so text received
from the remote side is never interpolated into a command line. Remote payloads
are only written to the command's stdin.

Consequences:

- Shell syntax such as `>` or `|` is not interpreted. Use
  `--copy-command "sh -c '...'"` if you really need a shell.
- The command is looked up in `PATH`. As with any local tool, a hijacked `PATH`
  or a malicious `wl-copy`/`xclip` earlier in `PATH` would execute attacker code.
  Use a trusted `PATH` and consider an absolute path
  (`--copy-command /usr/bin/wl-copy`).
- Do not set `OSC52_TEE_COPY_COMMAND` from an untrusted environment (for example
  a repository script or a remote shell).

## Terminal state

`osc52-tee` puts the real terminal into raw mode and restores it in a `finally`
block. If the process is killed with `SIGKILL`, or the terminal emulator
crashes, the terminal may be left in raw mode. Recover with:

```sh
reset
# or
stty sane
```

The tool does not run as root, does not need `sudo`, and has no setuid bits.

## Network

- `osc52-tee` itself opens no sockets and listens on no ports.
- `ossh` wraps your existing `ssh` process; OSC 52 payloads travel inside the
  SSH-encrypted channel.
- The `tail`-based workflow opens a second SSH connection and streams base64
  over it. The transport is encrypted, but the data is stored on the server as
  described above.

## Recommendations

1. Prefer `ossh` (local clipboard, no logs) over the server-side log workflow.
2. Only use OSC 52 bridging with hosts you trust.
3. Keep clipboard history disabled or short-lived if you copy secrets.
4. Clear the log files after debugging.
5. Keep `osc52-tee` and your clipboard utilities up to date.

## Reporting a vulnerability

Please open a **private security advisory** on GitHub rather than a public
issue, and include a minimal reproduction. There is no bug bounty and no
warranty; see [LICENSE](LICENSE).
