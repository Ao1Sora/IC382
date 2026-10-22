#!/bin/bash
# =====================================================================
# setup_new_wheeltec_lidar.sh
# Adds udev rules so non-standard Wheeltec lidar adapter boards
# (serial != 0001) are named /dev/wheeltec_lidar.
#
# Target : Jetson, Ubuntu 22.04, Wheeltec ROS2 image
# Usage  : sudo ./setup_new_wheeltec_lidar.sh          (install rules)
#          sudo ./setup_new_wheeltec_lidar.sh --scan   (list connected CH343 serials)
#          sudo ./setup_new_wheeltec_lidar.sh --remove (undo everything)
# Safe to re-run: the rules file is rewritten each time.
# =====================================================================

# ---- Add every lidar board serial that is NOT 0001 here -------------
SERIALS=(
  "5B8E674589"
  "5B8E671141"
  # "XXXXXXXXXX"
)
# ---------------------------------------------------------------------

RULES=/etc/udev/rules.d/wheeltec_lidar_local.rules
MIC=/etc/udev/rules.d/wheeltec_mic.rules

if [ "$EUID" -ne 0 ]; then
  echo "ERROR: run with sudo:  sudo $0 $*"
  exit 1
fi

reload_udev() {
  udevadm control --reload-rules
  udevadm trigger --action=add --subsystem-match=tty
  udevadm settle
}

case "$1" in
  --scan)
    echo "Connected CH343 serial devices:"
    found=0
    for dev in /dev/ttyCH343USB* /dev/ttyACM*; do
      [ -e "$dev" ] || continue
      s=$(udevadm info -a -n "$dev" | grep -m1 'ATTRS{serial}' | cut -d'"' -f2)
      echo "  $dev  serial=${s:-<none>}"
      found=1
    done
    [ "$found" -eq 0 ] && echo "  (none found)"
    echo
    echo "Known: 0001 = Wheeltec lidar, 0002 = Wheeltec controller."
    echo "Add any other lidar serial to SERIALS=(...) in this script."
    exit 0
    ;;
  --remove)
    rm -f "$RULES" /dev/wheeltec_lidar
    [ -f "$MIC.disabled" ] && mv "$MIC.disabled" "$MIC"
    reload_udev
    echo "Removed. Current devices:"
    ls -l /dev/wheeltec* 2>/dev/null || echo "  (no /dev/wheeltec* links)"
    exit 0
    ;;
esac

# ---- Install ---------------------------------------------------------
echo "Writing $RULES"
: > "$RULES"
for s in "${SERIALS[@]}"; do
  s="${s//$'\r'/}"   # strip stray Windows CR just in case
  [ -z "$s" ] && continue
  echo "KERNEL==\"ttyCH343USB*\", ATTRS{idVendor}==\"1a86\", ATTRS{idProduct}==\"55d4\", ATTRS{serial}==\"$s\", MODE:=\"0777\", GROUP:=\"dialout\", SYMLINK+=\"wheeltec_lidar\"" >> "$RULES"
  echo "KERNEL==\"ttyACM*\", ATTRS{idVendor}==\"1a86\", ATTRS{idProduct}==\"55d4\", ATTRS{serial}==\"$s\", MODE:=\"0777\", GROUP:=\"dialout\", SYMLINK+=\"wheeltec_lidar\"" >> "$RULES"
  echo "  + lidar serial $s"
done

# Catch-all mic rule tags every CH343 device (incl. lidar) as wheeltec_mic.
# Disable it unless the Wheeltec mic module is used.
if [ -f "$MIC" ]; then
  mv "$MIC" "$MIC.disabled"
  echo "Disabled $MIC (rename back to re-enable)"
fi

rm -f /dev/wheeltec_mic
reload_udev

echo
echo "Result:"
ls -l /dev/wheeltec* 2>/dev/null || echo "  (no /dev/wheeltec* links)"
echo
if [ -e /dev/wheeltec_lidar ]; then
  echo "OK: /dev/wheeltec_lidar -> $(readlink /dev/wheeltec_lidar)"
else
  echo "NOTE: /dev/wheeltec_lidar not present."
  echo "  - Wheelbase/lidar not connected right now? Rules are installed and will apply when it is."
  echo "  - Or the board's serial is not listed. Run:  sudo $0 --scan"
fi
