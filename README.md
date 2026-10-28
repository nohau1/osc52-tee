# osc52-tee

[![ci](https://github.com/nohau1/osc52-tee/actions/workflows/ci.yml/badge.svg)](https://github.com/nohau1/osc52-tee/actions/workflows/ci.yml)

**English** | [Русский](#osc52-tee-по-русски)

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

`install.sh` creates the target directory if it does not exist (default
`~/.local/bin`) and installs `osc52-tee` and `ossh` there. Override the prefix
with `PREFIX=/usr/local ./install.sh`.

### Add `~/.local/bin` to `PATH`

Check whether it is already there:

```sh
echo "$PATH" | tr ':' '\n' | grep -x "$HOME/.local/bin"
```

If nothing is printed, add it:

```sh
# bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
. ~/.bashrc

# zsh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
. ~/.zshrc

# fish
fish_add_path "$HOME/.local/bin"
```

Or let the installer update the profile of your current shell:

```sh
./install.sh --add-to-path
```

For login shells add the same line to `~/.profile`. On many distributions
`~/.local/bin` is added automatically once the directory exists, so opening a
new terminal after installation may be enough.

Verify:

```sh
command -v ossh
```

If you used a custom `PREFIX`, replace `~/.local/bin` with `$PREFIX/bin` above.

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

# osc52-tee по-русски

[English](#osc52-tee) | **Русский**

`osc52-tee` — небольшая обёртка без зависимостей, которая заставляет работать
копирование из удалённых терминальных приложений, когда ваш эмулятор терминала
игнорирует [OSC 52](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html#h3-Operating-System-Commands).

Она ставится между терминалом и `ssh` (или любым TUI), прозрачно пропускает все
байты и дублирует каждую запись буфера OSC 52 в:

- локальную clipboard-команду (`wl-copy`, `xclip`, `pbcopy`, `clip.exe`, ...);
- человекочитаемый лог;
- base64-поток, по одной строке на копию.

Обёрнутая программа ничего не замечает: не нужно патчить OpenCode, ставить
плагины или что-то менять на сервере.

```
terminal  <--->  osc52-tee  <--->  ssh  <--->  удалённый TUI
                     |
                     +--> wl-copy / xclip / pbcopy   (локальный буфер)
                     +--> clipboard.log               (tail -f)
                     +--> clipboard.b64               (строка на копию)
```

## Зачем это нужно

Многие терминалы либо вообще не реализуют OSC 52, либо запрещают запись в буфер
по умолчанию: GNOME Terminal/VTE, Apple Terminal, старые Konsole, xterm без
`allowWindowOps` и т.д. Удалённые TUI (OpenCode, vim, tmux) при этом продолжают
отправлять OSC 52 и показывать «Copied to clipboard», но до локального буфера
текст не доходит.

`osc52-tee` перехватывает последовательность **до** терминала и передаёт
декодированный текст локальной clipboard-утилите. По SSH это работает, потому
что OSC 52 идёт внутри зашифрованного SSH-потока.

Кому это нужно:

- вы работаете в GNOME Terminal, старом Konsole, xterm, Apple Terminal или
  MobaXterm;
- копируете из OpenCode/vim/tmux по SSH, а не только мышью;
- не хотите менять терминал или открывать веб-интерфейс;
- нужен клавиатурный Copy (`<leader>y`), а не выделение мышью с переносами строк.

Кому не нужно:

- у вас kitty/WezTerm/Ghostty/Windows Terminal — они понимают OSC 52 сами;
- вы копируете редко и вам достаточно `Shift` + выделение мышью;
- вам удобнее веб-версия OpenCode или desktop-приложение.

## Почему не плагин OpenCode

В TUI-плагинах OpenCode есть команды, keymap, данные сессий и клиент, но нет
хука на выделение и копирование: выделение обрабатывается внутри хоста TUI.
Поэтому перехват сделан на уровне байтового потока — ровно в тот момент, когда
OpenCode отправляет OSC 52 и показывает «Copied to clipboard». Это работает для
выделения мышью, `<leader>y`, `session.copy`, `session.copy.id`, «Copy path» и
любых других действий, потому что все они используют один и тот же writer.

## Установка

Требования: Python 3.9+ на машине, где находится буфер обмена. Сторонних
зависимостей нет.

```sh
git clone https://github.com/nohau1/osc52-tee.git
cd osc52-tee
./install.sh
```

`install.sh` сам создаёт каталог установки, если его нет (по умолчанию
`~/.local/bin`), и кладёт туда `osc52-tee` и `ossh`. Другой префикс:

```sh
PREFIX=/usr/local ./install.sh
```

### Добавление `~/.local/bin` в `PATH`

Проверьте, есть ли каталог в `PATH`:

```sh
echo "$PATH" | tr ':' '\n' | grep -x "$HOME/.local/bin"
```

Если пусто — добавьте:

```sh
# bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
. ~/.bashrc

# zsh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
. ~/.zshrc

# fish
fish_add_path "$HOME/.local/bin"
```

Или доверьте это установщику:

```sh
./install.sh --add-to-path
```

Для логин-шеллов добавьте ту же строку в `~/.profile`. Во многих дистрибутивах
`~/.local/bin` подхватывается автоматически, если каталог существует — после
установки может быть достаточно открыть новый терминал.

Проверка:

```sh
command -v ossh
```

Если использовали свой `PREFIX`, замените `~/.local/bin` на `$PREFIX/bin`.

## Быстрый старт: `ossh`

```sh
ossh user@server
```

Всё. `ossh` сам находит `wl-copy`, `xclip`, `pbcopy` или `clip.exe`, отключает
логи и запускает `ssh` под `osc52-tee`. Любое копирование внутри удалённой
сессии, включая выделение мышью в OpenCode, попадает в локальный буфер.

Используется как обычный `ssh`:

```sh
ossh -L 8080:localhost:8080 user@server
ossh -p 2222 user@server
```

Переопределить clipboard-команду:

```sh
OSSH_CLIP_CMD='xclip -selection clipboard -i' ossh user@server
```

Сократить ещё сильнее можно через `~/.ssh/config`:

```
Host srv
    HostName 203.0.113.10
    User me
```

```sh
ossh srv
```

> Не используйте `ossh` для `scp`/`rsync` — для них нужен обычный `ssh`/`scp`.

## Ручной запуск

```sh
# Wayland
osc52-tee --copy-command wl-copy --no-log --no-stream -- ssh server

# X11
osc52-tee --copy-command 'xclip -selection clipboard -i' --no-log --no-stream -- ssh server

# macOS
osc52-tee --copy-command pbcopy --no-log --no-stream -- ssh server
```

`--copy-command` разбирается через `shlex` и выполняется **без shell**. Для
редиректов и пайпов оберните явно:

```sh
osc52-tee --copy-command "sh -c 'cat >> /tmp/clipboard'" -- ssh server
```

## OpenCode на удалённом хосте

**Вариант A — автоматически в локальный буфер (рекомендуется).** Запускаете
`ossh server`, затем на сервере обычный `opencode`. Больше ничего ставить не
нужно.

**Вариант B — файл + `tail -f`.** Установите пример-лаунчер на сервере:

```sh
install -m 0755 examples/opencode/occlip ~/.local/bin/occlip
occlip
```

В другом терминале:

```sh
tail -f ~/.local/share/osc52-tee/clipboard.log
```

Каждая копия добавляет блок:

```
===== copy 2026-10-28 18:45:46 =====
...скопированный текст...
```

Дальше выделяете его в терминале и копируете штатным сочетанием терминала.

**Вариант C — автоматически, без обёртки ssh.** Стримите base64-файл в
локальный буфер:

```sh
ssh -T server 'tail -n0 -F ~/.local/share/osc52-tee/clipboard.b64' |
while IFS= read -r line; do
    [ -n "$line" ] && printf '%s' "$line" | base64 -d | wl-copy
done
```

### Нюансы для OpenCode

- OpenCode должен действительно отправлять OSC 52. Он проверяет terminfo
  capability `Ms`; держите `TERM` с `Ms` (`xterm-256color`, `tmux-256color`).
  Если OpenCode считает OSC 52 неподдерживаемым, он ничего не отправит, и
  обёртке будет нечего перехватывать.
- Работает для выделения мышью, `<leader>y`, `session.copy`, `session.copy.id`,
  «Copy path» и остальных действий копирования.
- Тост «Copied to clipboard» у OpenCode оптимистичный: он не знает, принял ли
  терминал последовательность. С обёрткой это перестаёт быть проблемой.

## Опции

| Опция | По умолчанию | Описание |
| --- | --- | --- |
| `--copy-command CMD` | — | Передавать каждую копию в stdin команды `CMD`. Разбор через `shlex`, без shell. |
| `--log FILE` | `~/.local/share/osc52-tee/clipboard.log` | Человекочитаемый лог. `''` отключает. |
| `--stream FILE` | `~/.local/share/osc52-tee/clipboard.b64` | Base64, одна строка на копию. `''` отключает. |
| `--no-log` | — | Отключить человекочитаемый лог. |
| `--no-stream` | — | Отключить base64-поток. |
| `--max-bytes N` | `1048576` | Игнорировать копии больше `N` байт после декодирования. |
| `--version` | — | Показать версию. |

Переменные окружения: `OSC52_TEE_COPY_COMMAND`, `OSC52_TEE_LOG`,
`OSC52_TEE_STREAM`, `OSC52_TEE_MAX_BYTES`. Старые имена `OPENCODE_*` тоже
поддерживаются.

## Как это работает

1. `osc52-tee` создаёт PTY и запускает дочерний процесс (`ssh`, `opencode`, ...)
   на slave-стороне.
2. Родительский процесс гоняет байты в обе стороны без изменений: raw mode,
   проброс размера окна, сигналы.
3. Потоковый парсер ищет в выводе `ESC ] 52 ; <target> ; <base64> BEL|ST`.
   Он умеет склеивать последовательность, разорванную между чтениями,
   понимает оба терминатора, игнорирует пустые очистки и `?`-запросы чтения.
4. Декодированные данные пишутся в лог/поток и ставятся в очередь к
   clipboard-команде. Ограниченная очередь и один воркер не дают устроить шторм
   процессов.
5. Исходные байты уходят в реальный терминал, поэтому терминалы с поддержкой
   OSC 52 продолжают работать как раньше.

OSC 52 **на чтение** не поддерживается: обёртка не имеет доступа к локальному
буферу и не отвечает на запросы.

## Безопасность

Коротко: **используйте только с серверами, которым доверяете.** Удалённый хост
может перезаписать ваш локальный буфер произвольным текстом — это свойство
самого OSC 52, а не этой реализации. Обёртка не умеет читать буфер, не открывает
сетевых портов и не исполняет данные с сервера.

Подробная модель угроз, риски логов и рекомендации — в [SECURITY.md](SECURITY.md)
(на английском).

- `--copy-command` — локальная настройка, выполняется без shell; текст с сервера
  попадает только в stdin.
- Очередь копий ограничена (16), воркер один, таймаут на команду — 10 секунд.
- Размер копии ограничен (1 МиБ по умолчанию), буфер парсера тоже ограничен.
- Логи создаются с правами `0600`, но всё равно содержат секреты. `ossh` логи
  отключает.
- Серверный вариант с `tail -f` хранит копии на диске **сервера**; для секретов
  лучше локальный буфер.
- При `SIGKILL` терминал может остаться в raw mode; лечится `reset` или
  `stty sane`.

## Ограничения

- Разбирается только «плоский» OSC 52. DCS-обёрнутые последовательности
  (tmux `allow-passthrough`, вложенные мультиплексоры) пробрасываются в
  терминал, но не дублируются в лог/буфер. При дефолтном
  `set-clipboard external` tmux сам переотправляет обычный OSC 52 — он
  обрабатывается.
- Программа должна отправлять OSC 52. Некоторые приложения отключают его, если
  считают терминал неподдерживающим.
- Лимиты размера OSC 52 зависят от терминала и утилит; 1 МиБ — консервативный
  дефолт.
- Linux протестирован; macOS должен работать (тот же `pty`/`termios`). Нативный
  Windows не поддерживается (используйте WSL или `clip.exe` из WSL).
- `ossh` добавляет слой PTY; полноэкранные приложения работают нормально, но
  это не замена `scp`/`rsync`.

## Разработка

```sh
make test    # 14 unit-тестов
make lint    # py_compile + sh -n
```

CI на GitHub гоняет те же тесты на Python 3.9 и 3.12, плюс проверку синтаксиса
shell-скриптов.

## Лицензия

MIT. См. [LICENSE](LICENSE).
