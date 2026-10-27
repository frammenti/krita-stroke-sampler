#!/usr/bin/env bash
set -euo pipefail

TYPES_DIR="typings"

STUBS="$(dpkg -L krita | grep '\.pyi$')"
USER="$(whoami)"

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

mkdir -p $TYPES_DIR
cd $TYPES_DIR

cp $STUBS krita.pyi
chown $USER:$USER krita.pyi

echo -e "Copied type stubs from \e[34m$STUBS\e[0m into \e[34m$TYPES_DIR/krita.pyi\e[0m"
