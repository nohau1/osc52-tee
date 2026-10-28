#!/bin/sh
# Install osc52-tee and ossh into $PREFIX/bin (default: ~/.local/bin).
#
# The target directory is created if it does not exist.
# See --add-to-path for updating your shell profile.
set -eu

cd "$(dirname "$0")"

PREFIX=${PREFIX:-"$HOME/.local"}
BINDIR="$PREFIX/bin"
ADD_TO_PATH=0

usage() {
    cat <<EOF
usage: ./install.sh [--add-to-path]

Installs osc52-tee and ossh into $BINDIR.
The directory is created if it does not exist.

  --add-to-path   append $BINDIR to PATH in your shell profile
  -h, --help      show this help
EOF
}

for arg in "$@"; do
    case "$arg" in
        --add-to-path) ADD_TO_PATH=1 ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            echo "unknown option: $arg" >&2
            usage >&2
            exit 2
            ;;
    esac
done

install -d "$BINDIR"
install -m 0755 bin/osc52-tee "$BINDIR/osc52-tee"
install -m 0755 bin/ossh "$BINDIR/ossh"

echo "installed:"
echo "  $BINDIR/osc52-tee"
echo "  $BINDIR/ossh"

in_path=0
case ":$PATH:" in
    *":$BINDIR:"*) in_path=1 ;;
esac

if [ "$in_path" -eq 1 ]; then
    echo
    echo "$BINDIR is already in PATH."
    exit 0
fi

if [ "$ADD_TO_PATH" -eq 1 ]; then
    shell_name=$(basename "${SHELL:-sh}")
    case "$shell_name" in
        fish)
            rc="$HOME/.config/fish/config.fish"
            mkdir -p "$(dirname "$rc")"
            line="fish_add_path \"$BINDIR\""
            ;;
        zsh)
            rc="$HOME/.zshrc"
            line="export PATH=\"$BINDIR:\$PATH\""
            ;;
        sh | dash)
            rc="$HOME/.profile"
            line="export PATH=\"$BINDIR:\$PATH\""
            ;;
        *)
            rc="$HOME/.bashrc"
            line="export PATH=\"$BINDIR:\$PATH\""
            ;;
    esac

    if [ -f "$rc" ] && grep -Fq "$BINDIR" "$rc"; then
        echo
        echo "$BINDIR is already mentioned in $rc; check it manually."
        exit 0
    fi

    {
        printf '\n# Added by osc52-tee install.sh\n'
        printf '%s\n' "$line"
    } >>"$rc"

    echo
    echo "added $BINDIR to PATH in $rc"
    echo "open a new terminal or run: . $rc"
    exit 0
fi

cat <<EOF

$BINDIR is not in PATH. Add it with one of:

  bash:  echo 'export PATH="$BINDIR:\$PATH"' >> ~/.bashrc && . ~/.bashrc
  zsh:   echo 'export PATH="$BINDIR:\$PATH"' >> ~/.zshrc && . ~/.zshrc
  fish:  fish_add_path "$BINDIR"

For login shells add the same line to ~/.profile.
Or rerun the installer with: ./install.sh --add-to-path
EOF
