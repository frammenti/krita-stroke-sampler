#!/usr/bin/env bash
set -euo pipefail

PLUGIN_DIR="plugin"
PYKRITA_DIR="$HOME/.local/share/krita/pykrita"

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

cp -r -f $PLUGIN_DIR/* $PYKRITA_DIR

echo -e "Installed plugin into \e[34m$PYKRITA_DIR\e[0m, restarting Krita…"

krita
