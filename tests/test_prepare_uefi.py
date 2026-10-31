"""Source patch preparation must be repeatable without replacing local edits."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare_uefi', ROOT / 'scripts/prepare-uefi.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class SourcePatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tree = self.root / 'uefi'
        self.tree.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.tree)], check=True)
        self.target = self.tree / 'entry.c'
        self.target.write_bytes(b'old entry\n')
        self.patch = self.root / 'entry.patch'
        self.patch.write_text('--- a/entry.c\n+++ b/entry.c\n@@ -1 +1 @@\n-old entry\n+saved entry arg\n')
        self.items = [{'path': 'entry.patch', 'sha256': prepare.digest(self.patch),
                       'files': {'entry.c': {
                           'before_sha256': hashlib.sha256(b'old entry\n').hexdigest(),
                           'after_sha256': hashlib.sha256(b'saved entry arg\n').hexdigest()}}}]

    def test_apply_and_repeat(self):
        plan = prepare.plan_source_patches(self.tree, self.root, self.items)
        self.assertEqual(prepare.apply_source_patches(self.tree, plan)[0]['state'], 'applied')
        plan = prepare.plan_source_patches(self.tree, self.root, self.items)
        self.assertEqual(prepare.apply_source_patches(self.tree, plan)[0]['state'], 'already-applied')
        self.assertEqual(self.target.read_bytes(), b'saved entry arg\n')

    def test_unknown_local_edit_is_preserved(self):
        self.target.write_bytes(b'local work\n')
        with self.assertRaises(ValueError):
            prepare.plan_source_patches(self.tree, self.root, self.items)
        self.assertEqual(self.target.read_bytes(), b'local work\n')

    def test_changed_patch_is_rejected_before_write(self):
        self.patch.write_text(self.patch.read_text() + 'tampered\n')
        with self.assertRaises(ValueError):
            prepare.plan_source_patches(self.tree, self.root, self.items)
        self.assertEqual(self.target.read_bytes(), b'old entry\n')


if __name__ == '__main__':
    unittest.main()
