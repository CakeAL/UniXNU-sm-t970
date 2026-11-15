#!/bin/sh
# Wait for Download Mode and flash one reviewed image into RECOVERY.
#
# Usage: flash-recovery-when-detected.sh IMAGE EXPECTED_SHA256 [TIMEOUT_SECONDS]
#
# Only the RECOVERY partition is ever written and the image must match the
# expected hash, so an unattended run cannot install an unreviewed build or
# touch BOOT/userdata/GPT. Exit 0 means "RECOVERY upload successful".
set -eu

image=$1
expected=$2
timeout=${3:-3600}
root=$(cd "$(dirname "$0")/.." && pwd)
heimdall="$root/.cache/heimdall/build/bin/heimdall"

[ -f "$image" ] || { echo "missing image: $image"; exit 1; }
actual=$(shasum -a 256 "$image" | cut -d' ' -f1)
[ "$actual" = "$expected" ] || { echo "hash mismatch: $actual"; exit 1; }
[ -x "$heimdall" ] || { echo "missing heimdall: $heimdall"; exit 1; }

deadline=$(( $(date +%s) + timeout ))
echo "waiting for Download Mode (image $expected, timeout ${timeout}s)"
while :; do
    if "$heimdall" detect 2>/dev/null | grep -q 'Device detected'; then
        break
    fi
    if [ "$(date +%s)" -ge "$deadline" ]; then
        echo "timeout: no Download Mode device"
        exit 2
    fi
    sleep 5
done

echo "device detected, flashing RECOVERY"
"$heimdall" flash --RECOVERY "$image" --no-reboot 2>&1 | tee "$image.flash.log"
grep -aq 'RECOVERY upload successful' "$image.flash.log" || { echo "flash did not report success"; exit 3; }
echo "flashed $expected"
