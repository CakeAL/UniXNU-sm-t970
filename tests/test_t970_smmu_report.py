import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class SmmuReportTests(unittest.TestCase):
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
