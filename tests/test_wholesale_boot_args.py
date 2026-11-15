#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'scripts/pack-wholesale-recovery.py'
spec = importlib.util.spec_from_file_location('pack_wholesale_recovery', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class BootArgs(unittest.TestCase):
    def test_exclusive_storage_routes(self):
        base = 'data-fua=1 native-ufs-root=1 '
        self.assertTrue(module.safe_command_line(base + 'sheng-data-persist=2'))
        self.assertTrue(module.safe_command_line(base + 'sheng-data-persist=0 t970-ufs-data=1 ufsrw=1'))
        self.assertFalse(module.safe_command_line(base + 'sheng-data-persist=2 t970-ufs-data=1'))
        self.assertFalse(module.safe_command_line(base + 'sheng-data-persist=0'))
        self.assertFalse(module.safe_command_line(base + 'sheng-data-persist=0 t970-ufs-data=1 sheng-data-persist=2'))
        self.assertFalse(module.safe_command_line(base + 'sheng-data-persist=0 t970-ufs-data=1 data-reset=1'))

if __name__ == '__main__':
    unittest.main()
