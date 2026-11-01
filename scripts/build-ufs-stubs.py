#!/usr/bin/env python3
"""Append the weak diagnostic stubs to the ShengUfs archive."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / 'build/sheng-ufs'
out.mkdir(parents=True, exist_ok=True)
source = ROOT / 'kits/sm-t970/UfsStubs.c'
obj = out / 'UfsStubs.o'
sdk = subprocess.check_output(['xcrun', '--sdk', 'iphoneos', '--show-sdk-path'], text=True).strip()
subprocess.run(['xcrun', 'clang', '-target', 'arm64-apple-ios17.0', '-isysroot', sdk, '-mkernel',
                '-miphoneos-version-min=17.0', '-Os', '-I', ROOT / '.cache/xnu-work/osfmk',
                '-c', source, '-o', obj], check=True)
subprocess.run(['xcrun', 'ar', 'rcs', out / 'libShengUfs.a', obj], check=True)
print('UFS stubs archived')
