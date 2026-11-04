#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
gcc -shared -fPIC -O2 scripts/rtx-cuda-proxy.c scripts/rtx-cuda-forward.S -o tools/rtx-cuda-proxy-new.so -ldl -lpthread -Wl,-soname,libcuda.so.1
mv tools/rtx-cuda-proxy-new.so tools/rtx-cuda-proxy.so
