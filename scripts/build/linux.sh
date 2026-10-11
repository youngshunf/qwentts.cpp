#!/bin/sh
set -eu
exec python3 "$(dirname "$0")/build-library.py" --platform linux-x86_64 "$@"
