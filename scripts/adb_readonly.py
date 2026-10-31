"""Binary-safe reads through the already installed su on the one USB device."""
import shlex
import subprocess


def read(command):
    result = subprocess.run(["adb", "-d", "shell", "-T", "su -c " + shlex.quote(command)],
                            capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace") or
                           f"ADB command failed ({result.returncode}): {command}")
    return result.stdout
