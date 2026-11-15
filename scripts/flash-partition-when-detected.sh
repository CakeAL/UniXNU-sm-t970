#!/bin/sh
# Wait for Download Mode and flash one reviewed file into RECOVERY or CACHE.
#
# Usage: flash-partition-when-detected.sh PARTITION IMAGE EXPECTED_SHA256 [TIMEOUT_SECONDS]
#
# PARTITION is RECOVERY (the boot image) or CACHE (the second-volume payload).
# Nothing else is writable through this script: BOOT, userdata, super and the
# GPT stay untouched, and the file must match the expected hash, so an
# unattended run cannot install an unreviewed build.
set -eu

partition=$1
image=$2
expected=$3
timeout=${4:-3600}
root=$(cd "$(dirname "$0")/.." && pwd)
heimdall="$root/.cache/heimdall/build/bin/heimdall"

case "$partition" in
    RECOVERY|CACHE) ;;
    *) echo "refusing partition: $partition (only RECOVERY and CACHE)"; exit 1 ;;
esac

[ -f "$image" ] || { echo "missing image: $image"; exit 1; }
actual=$(shasum -a 256 "$image" | cut -d' ' -f1)
[ "$actual" = "$expected" ] || { echo "hash mismatch: $actual"; exit 1; }
[ -x "$heimdall" ] || { echo "missing heimdall: $heimdall"; exit 1; }

deadline=$(( $(date +%s) + timeout ))
echo "waiting for Download Mode (partition $partition, image $expected, timeout ${timeout}s)"
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

echo "device detected, flashing $partition"
"$heimdall" flash "--$partition" "$image" --no-reboot 2>&1 | tee "$image.flash.log"
grep -aq "$partition upload successful" "$image.flash.log" || { echo "flash did not report success"; exit 3; }
echo "flashed $expected into $partition"
