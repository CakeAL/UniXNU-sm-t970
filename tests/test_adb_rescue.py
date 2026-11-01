import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('adb_rescue', ROOT / 'scripts/build-adb-rescue.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def entry(name, content):
    return (name, [1, 0o100644, 0, 0, 1, 0, len(content), 0, 0, 0, 0, len(name)+1, 0], content)


class RescueTests(unittest.TestCase):
    def test_archive_preservation_and_disabled_recovery(self):
        entries = [entry('system/etc/init/hw/init.rc', b'service recovery /system/bin/recovery\n    user root\n'),
                   entry('prop.default', b'\nro.secure=1\nro.debuggable=0\nro.adb.secure=1\n'),
                   entry('system/bin/untouched', b'\0\1\xffpayload')]
        changed, names = MODULE.modify(entries)
        self.assertEqual(MODULE.unpack_cpio(MODULE.pack_cpio(changed)), changed)
        self.assertEqual(changed[2], entries[2])
        self.assertEqual(len(names), 2)
        self.assertIn(b'service recovery /system/bin/recovery\n    disabled\n', changed[0][2])
        self.assertIn(b'setprop sys.usb.config adb', changed[0][2])
        self.assertIn(b'ro.adb.secure=0', changed[1][2])
        with self.assertRaises(ValueError):
            MODULE.modify(entries[:1])
        with self.assertRaises(ValueError):
            MODULE.unpack_cpio(b'bad archive')
        with self.assertRaises(ValueError):
            MODULE.unpack_cpio(MODULE.pack_cpio([entry('../escape', b'x')]))
