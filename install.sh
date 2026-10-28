#!/bin/sh
# Install osc52-tee and ossh into $PREFIX/bin (default: ~/.local/bin).
set -eu

PREFIX=${PREFIX:-"$HOME/.local"}
BINDIR="$PREFIX/bin"

install -d "$BINDIR"
install -m 0755 bin/osc52-tee "$BINDIR/osc52-tee"
install -m 0755 bin/ossh "$BINDIR/ossh"

echo "installed:"
echo "  $BINDIR/osc52-tee"
echo "  $BINDIR/ossh"

case ":$PATH:" in
    *":$BINDIR:"*) ;;
    *) echo "note: $BINDIR is not in PATH; add it to your shell profile" ;;
esac
