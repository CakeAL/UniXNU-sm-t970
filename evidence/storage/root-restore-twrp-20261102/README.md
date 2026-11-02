# Restore after owner deleted UserData (2026-11-02)

Owner asked to flash the image through TWRP, asked about the large image, then
confirmed deleting UserData. Initial read-only audit found the oldBOOT prefix and
newTWRP correct, but root header different and two known nonzero root blocks zero.
The old full-root verification therefore did not describe current storage.

Unmounted /sdcard and /data normally. Root TWRP identity, exact sda36 geometry
and unmounted checks passed. The checker now additionally accepts only the exact
SAMSUNG_gts7xlwifi model + gts7xlwifi product pair, with regression refusals.

Restored original9382658048-byte root prefix: write/sync/BLKFLSBUF succeeded;
complete readback SHA256 matches fd43ee7035ce185ce4215ac93fdc006fd784a54b3b7442e21457c226cbe03093.
Both carrier ranges also differed; both old payloads backed up before either
write, then corrected manifests written/synced/flushed and completely verified.
Their unchanged anchors/tables were previously RSA + all-block C verified.

BOOT17bda459 was pushed with remote hash check, written/synced/flushed, then all
62713856 bytes read back identical. Reboot requested13:37:16+08 successfully.
This is the after-init-exec6second reset diagnostic, not a normal boot image.
Startup observation pending. No repartition, formatting or new writableData layout.

Raw BOOT/RECOVERY backups and carrier backups stay in ignored out/ directories.
Recovery full readback independently confirmed the prior TWRP upload despite its
session-end error. Root deletion is not proof of the prior bootloader-only cause.
