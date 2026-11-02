import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('recovery_check', ROOT / 'scripts/check-recovery-storage.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RecoveryReadinessTests(unittest.TestCase):
    def test_twrp_requires_exact_model_and_product_pair(self):
        good = dict(model='SAMSUNG_gts7xlwifi', product='gts7xlwifi',
                    identity='uid=0(root) gid=0(root)', target='/dev/block/sda36',
                    size='243668070400', logical='4096', device_mm='259:20',
                    mounts='1 0 0:1 / / rw - rootfs rootfs rw')
        self.assertEqual(MODULE.validate(**good), [])
        for changes in ({'product': ''}, {'product': 'gts7wifi'},
                        {'model': 'SAMSUNG_gts7wifi'}, {'model': 'SM-T733'}):
            with self.subTest(changes=changes):
                self.assertTrue(MODULE.validate(**dict(good, **changes)))

    def test_identity_geometry_and_mounts_fail_closed(self):
        good = dict(model='SM-T970', identity='uid=0(root) gid=0(root)', target='/dev/block/sda36',
                    size='243668070400', logical='4096', device_mm='259:20', mounts='1 0 0:1 / / rw - rootfs rootfs rw')
        self.assertEqual(MODULE.validate(**good), [])
        for field, bad in [('model', 'SM-T733'), ('identity', 'uid=2000(shell)'),
                           ('target', '/dev/block/sda23'), ('size', '999'), ('logical', '512'),
                           ('mounts', '1 0 259:20 / /mnt/something rw - ext4 /dev/alias rw'),
                           ('mounts', '1 0 253:0 / /data rw - f2fs /dev/dm-0 rw')]:
            with self.subTest(field=field, value=bad):
                self.assertTrue(MODULE.validate(**dict(good, **{field: bad})))
