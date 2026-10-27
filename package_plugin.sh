#!/usr/bin/env bash
set -euo pipefail

PLUGIN_DIR="plugin"
PLUGIN_NAME="stroke_sampler"

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

cd $PLUGIN_DIR
zip -r ../${PLUGIN_NAME}.zip . -x "$PLUGIN_NAME/__pycache__/*"

echo -e "Packaged plugin into \e[34m$PLUGIN_NAME.zip\e[0m"
