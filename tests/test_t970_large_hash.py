import gzip
import hashlib
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / 'drivers/ShengUfs/T970LargeData.h'
BACKUP = ROOT / 'out/dual-system/data-backup-20261115/data-before-reference-test.gz'

class HeaderIdentityTest(unittest.TestCase):
    def test_seed_literal_matches_generated_seed(self):
        source = HEADER.read_text()
        body = re.search(r'kT970LargeSeed\[32\]\s*=\s*\{([^}]+)\}', source).group(1)
        value = bytes(int(n, 16) for n in re.findall(r'0x([0-9a-fA-F]{2})', body))
        self.assertEqual(value.hex(), 'd4372c71be216bed6f8278026fb6bd08d52fa7565fed0276a9be8fffac8b2cb9')

    def test_literal_matches_device_evidence(self):
        source = HEADER.read_text()
        body = re.search(r'kT970DirectHeaderHash\[32\]\s*=\s*\{([^}]+)\}', source).group(1)
        value = bytes(int(n, 16) for n in re.findall(r'0x([0-9a-fA-F]{2})', body))
        self.assertEqual(value.hex(), 'f1d880ae3bb4ad6b874c44dda3a1782724622c144ad56be0d24385108db94d0f')
        if BACKUP.is_file():
            with gzip.open(BACKUP, 'rb') as f:
                self.assertEqual(value, hashlib.sha256(f.read(4096)).digest())

if __name__ == '__main__':
    unittest.main()
