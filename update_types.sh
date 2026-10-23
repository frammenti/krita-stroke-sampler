#!/usr/bin/env bash
set -euo pipefail

TYPES_DIR="typings"

STUBS="$(dpkg -L krita | grep '\.pyi$')"
USER="$(whoami)"

blue=$(tput setaf 4)
normal=$(tput sgr0)

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

mkdir -p $TYPES_DIR
cd $TYPES_DIR

cp $STUBS krita.pyi
chown $USER:$USER krita.pyi

echo "Copied type stubs from ${blue}$STUBS${normal} into ${blue}$TYPES_DIR/krita.pyi${normal}"