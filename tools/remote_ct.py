"""
Run a supplied Python program in CT120 through the existing Proxmox SSH route.

No credentials, persistent transport changes or remote files are introduced.
"""

import os
import shutil
import subprocess
import sys

# ruff: noqa: INP001 - standalone operator script, not an import package


def run(source: str) -> subprocess.CompletedProcess:
    """Execute in the configured existing SSH/LXC route without changing it."""
    host = os.environ["BYPARR_PROXMOX_HOST"]
    ct_id = int(os.environ.get("BYPARR_CT_ID", "120"))
    ssh = shutil.which("ssh")
    if ssh is None:
        message = "OpenSSH client is required"
        raise RuntimeError(message)
    return subprocess.run(  # noqa: S603 - operator host, integer CT id, no local shell
        [ssh, "-o", "BatchMode=yes", f"root@{host}", f"pct exec {ct_id} -- python3 -"],
        input=source,
        text=True,
        check=False,
    )


if __name__ == "__main__":
    raise SystemExit(run(sys.stdin.read()).returncode)
