import pathlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class SmmuReportTests(unittest.TestCase):
    def test_sm8250_clock_offsets_against_recorded_target_source(self):
        source = json.loads((ROOT / 'evidence/storage/handoff-readonly/clock-source.json').read_text())
        header = (ROOT / 'package/ShengUfs/GccUfs.h').read_text()
        for name, clock in source['clocks'].items():
            value = re.search(r'^#define\s+' + name + r'\s+(0x[0-9a-fA-F]+)', header, re.MULTILINE)
            self.assertIsNotNone(value, name)
            self.assertEqual(int(value[1], 16), int(clock['offset'], 16), name)
        self.assertNotIn('GCC_UFS_MEM_PHY_GDSCR', header)

    def test_handoff_gates_and_full_table_display(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = pathlib.Path(temporary) / 'handoff-test'
            subprocess.run(['clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-Wno-unused-function', '-I', str(ROOT / 'package/ShengUfs'),
                            str(ROOT / 'tests/cpp/t970-ufs-handoff.cpp'), '-o', str(executable)], check=True)
            result = subprocess.run([str(executable)], text=True, capture_output=True, check=True)
            self.assertIn('PASS: handoff clock gates', result.stdout)

    def test_register_model_and_bounded_reads(self):
        compiler = shutil.which('clang++')
        self.assertIsNotNone(compiler, 'clang++ is needed for the SMMU model test')
        with tempfile.TemporaryDirectory() as temporary:
            executable = pathlib.Path(temporary) / 'report-test'
            subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-Wno-unused-function', '-I', str(ROOT / 'package/ShengUfs'),
                            str(ROOT / 'tests/cpp/t970-smmu-report.cpp'), '-o', str(executable)], check=True)
            result = subprocess.run([str(executable)], text=True, capture_output=True, check=True)
            self.assertIn('PASS: 11', result.stdout)


if __name__ == '__main__':
    unittest.main()
