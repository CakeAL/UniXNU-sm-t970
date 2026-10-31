#!/usr/bin/env python3
"""Compile the unbooted board firmware for host review, using UniXNU's builder.

This development check leaves board.example enabled, never builds an XNU kernel
or Android boot image, and never operates the device. Use the normal CLI once
the launch/handoff inputs have passed their separate hardware checks.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    device = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unixnu", type=Path, default=device.parent / "UniXNU")
    parser.add_argument("--uefi", type=Path, required=True)
    parser.add_argument("--extract-dir", type=Path, required=True)
    args = parser.parse_args()
    subprocess.run([sys.executable, device / "scripts/prepare-uefi.py", "--uefi", args.uefi,
                    "--extract-dir", args.extract_dir], check=True)
    sys.path.insert(0, str(args.unixnu.resolve() / "scripts"))
    from unixnu.cli import parser as cli_parser
    from unixnu.config import Context
    from unixnu import feeds, firmware, tree
    ctx = Context(cli_parser().parse_args(["build", "firmware", "-D", str(device)]))
    expected = json.loads((device / "evidence/shared-support/selection.json").read_text())["framework"]["revision"]
    revision = subprocess.check_output(["git", "-C", str(args.unixnu), "rev-parse", "HEAD"], text=True).strip()
    if revision != expected:
        parser.error("UniXNU differs from the reviewed revision")
    modules = feeds.resolve(ctx)
    tree.assemble(ctx, modules)
    # Exercise the real firmware implementation only. The CLI's kernel/bootimg
    # example checks remain enabled and are not changed by this development tool.
    uefi = args.uefi.resolve()
    fd = firmware.build(ctx, modules, uefi, uefi / "Mu_Basecore")
    report = {"scope": "Host-built firmware candidate only; no kernel, boot image or device execution",
              "device_revision": subprocess.check_output(["git", "-C", str(device), "rev-parse", "HEAD"], text=True).strip(),
              "uncommitted_changes": bool(subprocess.check_output(["git", "-C", str(device), "status", "--porcelain"], text=True).strip()),
              "framework_revision": revision, "fd_bytes": fd.stat().st_size,
              "fd_sha256": hashlib.sha256(fd.read_bytes()).hexdigest(), "hardware_tested": False}
    output = device / "out/uefi-candidate/result.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print("Built firmware candidate; report: " + str(output))


if __name__ == "__main__":
    main()
