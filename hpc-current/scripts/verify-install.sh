#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for attempt in $(seq 1 1200); do
  [[ -f logs/install-state.txt ]] && break
  sleep 3
done
[[ -f logs/install-state.txt ]]
install="$PWD/tools/isaacsim-4.5.0"
find "$install" -maxdepth 1 -name '*.sh' -exec chmod +x {} +
printf '\nNATIVE PYTHON CHECK\n'
if "$install/python.sh" -c 'import sys; print(sys.version)' > logs/native-python.log 2>&1; then
  echo 'NATIVE_PYTHON_OK'
else
  cat logs/native-python.log
fi
printf '\nNATIVE POST INSTALL\n'
(cd "$install" && ./post_install.sh)
printf '\nNATIVE PYTHON CHECK\n'
scripts/isaac-python.sh -c 'import sys; print(sys.version)'
printf '\nPHYSICS AND RENDERING CHECK\n'
timeout 1200 scripts/isaac-python.sh "$PWD/scripts/smoke-test.py" > logs/smoke-test.log 2>&1
if grep -q IC382_SMOKE_TEST_PASSED logs/smoke-test.log; then
  grep IC382_SMOKE_TEST_PASSED logs/smoke-test.log
  printf 'VERIFIED\n' > logs/verify-state.txt
else
  tail -60 logs/smoke-test.log
  exit 1
fi
