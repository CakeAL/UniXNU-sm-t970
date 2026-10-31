#!/usr/bin/env python3
"""Stage the committed SM-T970 overlay and exact local stock binary inputs.

Use a dedicated Mu-Silicium checkout at the pinned revision. This only prepares
host files; it does not build, boot or flash, or remove board.example.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def revision(path):
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan_source_patches(uefi, source, patches):
    plan = []
    for item in patches:
        patch = source / item["path"]
        if not patch.is_file() or digest(patch) != item["sha256"]:
            raise ValueError("Missing/mismatched firmware patch: " + str(patch))
        states = []
        for relative, hashes in item["files"].items():
            target = uefi / relative
            if not target.is_file():
                raise ValueError("Missing firmware source: " + relative)
            current = digest(target)
            states.append("pending" if current == hashes["before_sha256"] else
                          "applied" if current == hashes["after_sha256"] else "modified")
        if not states or len(set(states)) != 1 or states[0] == "modified":
            raise ValueError("Firmware patch pre/postimages differ; preserve and inspect local edits: " + item["path"])
        command = ["git", "-C", str(uefi), "apply", "--check"]
        if states[0] == "applied":
            command.append("--reverse")
        check = subprocess.run(command + [str(patch.resolve())], capture_output=True)
        if check.returncode:
            raise ValueError("Firmware patch check failed: " + check.stderr.decode(errors="replace"))
        plan.append((item, patch, states[0]))
    return plan


def apply_source_patches(uefi, plan):
    result = []
    for item, patch, state in plan:
        if state == "pending":
            subprocess.run(["git", "-C", str(uefi), "apply", str(patch.resolve())], check=True)
        for relative, hashes in item["files"].items():
            if digest(uefi / relative) != hashes["after_sha256"]:
                raise ValueError("Firmware patch postimage mismatch: " + relative)
        result.append({"path": item["path"], "sha256": item["sha256"],
                       "state": "already-applied" if state == "applied" else "applied"})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uefi", type=Path, required=True)
    parser.add_argument("--extract-dir", type=Path, required=True)
    args = parser.parse_args()
    device = Path(__file__).resolve().parents[1]
    source = device / "package/firmware"
    inputs = json.loads((source / "inputs.json").read_text())
    uefi = args.uefi.resolve()
    if revision(uefi) != inputs["revision"]:
        parser.error("Mu-Silicium revision differs from inputs.json")
    for path, expected in inputs["submodules"].items():
        if revision(uefi / path) != expected:
            parser.error("Submodule revision differs: " + path)
    stock = json.loads((device / "evidence/device-inputs/boot-firmware.json").read_text())
    if stock["device"]["model"] != "SM-T970":
        parser.error("Unexpected stock input identity")
    try:
        patch_plan = plan_source_patches(uefi, source, inputs.get("patches", []))
    except ValueError as error:
        parser.error(str(error))
    manifest = uefi / ".unixnu-sm-t970-stage.json"
    previous = json.loads(manifest.read_text()).get("files", {}) if manifest.exists() else {}
    staged = {}
    for path in sorted(source.rglob("*")):
        if path.is_file() and path.relative_to(source).parts[0] in ("Resources", "Platforms"):
            staged[str(path.relative_to(source))] = path.read_bytes()
    for entry in inputs["inputs"]:
        path = args.extract_dir / entry["source"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            parser.error("Missing/mismatched stock binary: " + str(path))
        staged[entry["destination"]] = path.read_bytes()
    # Check all destinations before writing. Reruns may update only files that
    # still match the last preparation manifest; preserve unrelated local edits.
    for relative, data in staged.items():
        target = uefi / relative
        if target.exists() and target.read_bytes() != data:
            if hashlib.sha256(target.read_bytes()).hexdigest() != previous.get(relative):
                parser.error("Refusing to overwrite an independently modified file: " + str(target))
    try:
        patch_results = apply_source_patches(uefi, patch_plan)
    except ValueError as error:
        parser.error(str(error))
    for relative, data in staged.items():
        target = uefi / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    report = {"upstream_revision": inputs["revision"], "device_revision": revision(device),
              "scope": "Host staging only; runtime evidence is recorded separately",
              "source_patches": patch_results,
              "files": {p: hashlib.sha256(data).hexdigest() for p, data in staged.items()}}
    manifest.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Staged {len(staged)} files, including {len(inputs['inputs'])} stock inputs; verified {len(patch_results)} source patches")


if __name__ == "__main__":
    main()
