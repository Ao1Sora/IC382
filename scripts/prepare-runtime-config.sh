#!/usr/bin/env bash
# Generate machine-local configuration; existing runtime files are preserved.
set -euo pipefail
project=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project"
mkdir -p cache logs tools
if [[ ! -f cache/course-passwd ]]; then
  cp /etc/passwd cache/course-passwd
  entry=$(getent passwd "$(id -u)")
  grep -q ":$(id -u):" cache/course-passwd || printf '%s\n' "$entry" >>cache/course-passwd
fi
[[ -f cache/course-hosts ]] || cp /etc/hosts cache/course-hosts
[[ -f cache/course-dds.xml ]] || cp config/course-dds.xml cache/course-dds.xml
echo 'Runtime directories and local configuration ready.'
