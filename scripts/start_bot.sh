#!/bin/sh

set -eu

python3 scripts/init_runtime_database.py
exec python3 src/main.py
