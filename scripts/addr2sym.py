#!/usr/bin/env python3
"""Map kernel addresses printed by the boot page to the nearest symbol below them.

The page prints unslid link addresses (0xfffffff0...), which is exactly what the
unstripped kernel's symbol table uses, so no slide arithmetic is needed.
"""
import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT = Path("/Users/cakeal/vsc/UniXNU/out/sm-t970/ipados-17.7.11-21H461/gts7xlwifi")
KERNEL = DEFAULT / "tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837.unstripped.noctf"


def symbols(kernel: Path) -> list[tuple[int, str]]:
    out = subprocess.run(["nm", "-n", str(kernel)], capture_output=True, text=True, check=True).stdout
    table = []
    for line in out.splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) != 3:
            continue
        try:
            table.append((int(parts[0], 16), parts[2]))
        except ValueError:
            continue
    table.sort()
    return table


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("addresses", nargs="+", help="addresses as printed, e.g. fffffff007a2ceac")
    parser.add_argument("--kernel", type=Path, default=KERNEL)
    args = parser.parse_args()
    table = symbols(args.kernel)
    addrs = [int(a, 16) for a in args.addresses]
    for addr in addrs:
        index = None
        for i, (value, _) in enumerate(table):
            if value <= addr:
                index = i
            else:
                break
        if index is None:
            print(f"{addr:016x}  ?")
            continue
        value, name = table[index]
        print(f"{addr:016x}  {name}+0x{addr - value:x}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
