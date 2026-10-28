# osc52-tee

[![ci](https://github.com/nohau1/osc52-tee/actions/workflows/ci.yml/badge.svg)](https://github.com/nohau1/osc52-tee/actions/workflows/ci.yml)

A tiny, dependency-free PTY wrapper that makes **copy from remote terminal apps**
work when your terminal emulator ignores [OSC 52](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h3-Operating-System-Commands).

It sits between your terminal and `ssh` (or any TUI), transparently forwards
all bytes, and mirrors every OSC 52 clipboard write to:

- a local clipboard command (`wl-copy`, `xclip`, `pbcopy`, `clip.exe`, ...);
- a human-readable log file;
- a base64 stream, one line per copy.

The wrapped program never notices: no patching, no plugins, no server-side
changes.

```
terminal  <--->  osc52-tee  <--->  ssh  <--->  remote TUI
                     |
                     +--> wl-copy / xclip / pbcopy   (local clipboard)
                     +--> clipboard.log               (tail -f)
                     +--> clipboard.b64               (one line per copy)
```

## Why

Many terminals do not implement OSC 52 at all, or disable clipboard writes by
default (GNOME Terminal/VTE, Apple Terminal, older Konsole, xterm without
`allowWindowOps`, ...). Remote TUIs such as OpenCode, vim or tmux still send
OSC 52 and show a "Copied to clipboard" notification, but nothing reaches the
local clipboard.

`osc52-tee` intercepts the sequence **before** it reaches the terminal and
feeds the decoded text to a local clipboard tool. It works over SSH because
OSC 52 travels inside the encrypted SSH stream.

## Install

Requirements: Python 3.9+ on the machine that owns the clipboard. No third-party
packages.

```sh
git clone https://github.com/nohau1/osc52-tee.git
cd osc52-tee
./install.sh
```

`install.sh` copies `osc52-tee` and `ossh` to `~/.local/bin` (override with
`PREFIX=/usr/local ./install.sh`). Make sure that directory is in `PATH`.

## Usage

### Recommended: `ossh`

```sh
ossh user@server
```

That is it. `ossh` detects `wl-copy`, `xclip`, `pbcopy` or `clip.exe`, disables
the log files, and runs `ssh` under `osc52-tee`. Every copy inside the remote
session, including mouse selection in OpenCode, lands in the local clipboard.

Use it exactly like `ssh`:

```sh
ossh -L 8080:localhost:8080 user@server
ossh -p 2222 user@server
```

Override the clipboard tool:

```sh
OSSH_CLIP_CMD='xclip -selection clipboard -i' ossh user@server
```

Add a host alias to `~/.ssh/config` to shorten it further:

```
Host srv
    HostName 203.0.113.10
    User me
```

```sh
ossh srv
```

> Do not use `ossh` for `scp`/`rsync`; use plain `ssh`/`scp` there.

### Manual

```sh
# Wayland
osc52-tee --copy-command wl-copy --no-log --no-stream -- ssh server

# X11
osc52-tee --copy-command 'xclip -selection clipboard -i' --no-log --no-stream -- ssh server

# macOS
osc52-tee --copy-command pbcopy --no-log --no-stream -- ssh server
```

`--copy-command` is parsed with `shlex` and executed **without a shell**. For
redirections or pipes, wrap it explicitly:

```sh
osc52-tee --copy-command "sh -c 'cat >> /tmp/clipboard'" -- ssh server
```

### OpenCode on a remote host

**Option A — automatic local clipboard (recommended).** Run `ossh server`, then
start `opencode` on the server as usual. Nothing else to install or configure.

**Option B — file + `tail -f`.** Install the example launcher on the server:

```sh
install -m 0755 examples/opencode/occlip ~/.local/bin/occlip
occlip
```

Then in another terminal:

```sh
tail -f ~/.local/share/osc52-tee/clipboard.log
```

Each copy appends a block:

```
===== copy 2026-10-28 18:45:46 =====
...copied text...
```

Select it in the terminal and copy with the terminal's own shortcut.

**Option C — automatic clipboard without wrapping ssh.** Stream the base64 file
to the local clipboard:

```sh
ssh -T server 'tail -n0 -F ~/.local/share/osc52-tee/clipboard.b64' |
while IFS= read -r line; do
    [ -n "$line" ] && printf '%s' "$line" | base64 -d | wl-copy
done
```

### Notes for OpenCode

- OpenCode must actually emit OSC 52. It checks the terminfo `Ms` capability;
  keep `TERM` set to something with `Ms` (`xterm-256color`, `tmux-256color`).
  If OpenCode thinks OSC 52 is unsupported, it sends nothing and the wrapper
  has nothing to mirror.
- Works for mouse selection, `<leader>y`, `session.copy`, `session.copy.id`,
  "Copy path" and every other copy action, because they all use the same
  writer.
- OpenCode's "Copied to clipboard" toast is optimistic; it cannot know whether
  the terminal honoured the sequence. The wrapper makes it true.

## Options

| Option | Default | Description |
| --- | --- | --- |
| `--copy-command CMD` | — | Feed each decoded copy to `CMD`'s stdin. Parsed with `shlex`, no shell. |
| `--log FILE` | `~/.local/share/osc52-tee/clipboard.log` | Human-readable log. `''` disables. |
| `--stream FILE` | `~/.local/share/osc52-tee/clipboard.b64` | Base64 line per copy. `''` disables. |
| `--no-log` | — | Disable the human-readable log. |
| `--no-stream` | — | Disable the base64 stream. |
| `--max-bytes N` | `1048576` | Ignore copies larger than `N` bytes after decoding. |
| `--version` | — | Print the version. |

Environment variables: `OSC52_TEE_COPY_COMMAND`, `OSC52_TEE_LOG`,
`OSC52_TEE_STREAM`, `OSC52_TEE_MAX_BYTES`. The legacy `OPENCODE_*` names are
still accepted.

## How it works

1. `osc52-tee` allocates a PTY and runs the child (`ssh`, `opencode`, ...) on
   the slave side.
2. The parent pumps bytes in both directions without modification (raw mode,
   window-size propagation, signals).
3. A streaming parser scans the child's output for
   `ESC ] 52 ; <target> ; <base64> BEL|ST`. It handles sequences split across
   reads, both terminators, and ignores empty clears and `?` read queries.
4. Decoded payloads are written to the log/stream and queued for the clipboard
   command. A bounded queue and a single worker prevent process storms.
5. The original bytes are forwarded to the real terminal, so terminals that do
   support OSC 52 keep working as before.

OSC 52 **reads** are never answered: the wrapper has no access to the local
clipboard and does not implement read queries.

## Security

Short version: **use it only with servers you trust.** A remote host can
overwrite your local clipboard with arbitrary text; that is inherent to OSC 52,
not specific to this tool. The wrapper cannot read your clipboard, does not
open network ports, and does not execute remote data.

Read [SECURITY.md](SECURITY.md) for the full threat model, logging risks and
hardening advice.

## Limitations

- Only plain OSC 52 is parsed. DCS-wrapped sequences (tmux
  `allow-passthrough`, nested multiplexers) are forwarded to the terminal but
  not mirrored. With tmux's default `set-clipboard external`, tmux itself
  re-emits plain OSC 52, which is handled.
- The wrapped program must emit OSC 52. Some programs disable it when they
  believe the terminal does not support it.
- OSC 52 payload limits vary by terminal/tool; 1 MiB is a conservative default.
- Linux is tested; macOS should work (same `pty`/`termios` API). Native Windows
  is not supported (use WSL, or `clip.exe` from WSL).
- `ossh` adds a PTY layer; full-screen apps are fine, but don't use it as a
  drop-in for `scp`/`rsync`.

## Development

```sh
python3 -m unittest discover -s tests -v
```

The test suite covers the streaming parser (BEL/ST, split reads, malformed
base64, size limits), the clipboard worker and the log/stream writers.

## License

MIT. See [LICENSE](LICENSE).

---

## Кратко по-русски

`osc52-tee` — обёртка вокруг `ssh`/TUI, которая перехватывает OSC 52 и кладёт
скопированный текст в локальный буфер (или в лог), даже если терминал OSC 52
не поддерживает.

```sh
./install.sh          # в ~/.local/bin
ossh user@server      # дальше работаете как обычно
```

На сервере ничего устанавливать не нужно. Для OpenCode: запускайте `opencode`
внутри `ossh`-сессии, и выделение мышью/`<leader>y` сразу попадает в локальный
буфер. Подробности и вариант с `tail -f` — в разделах выше.
