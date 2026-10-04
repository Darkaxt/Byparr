"""Focused contracts for the existing MiniPC maintenance integration."""

import re
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1] / "tools/update_minipc_leftover_services.sh"
)


class ServerMaintenanceTests(unittest.TestCase):
    def test_reviewed_local_byparr_is_not_registry_updated(self):
        calls = re.findall(r"^compose_update (\S+)", SCRIPT.read_text(), re.MULTILINE)
        self.assertNotIn("byparr", calls)
        self.assertEqual(
            calls,
            [
                "tor-proxy", "prowlarr", "unpackerr", "houndarr",
                "audiomuse-ai", "tunelog", "lidaclips",
            ],
        )

    def test_byparr_monitoring_is_browser_free_and_requires_success(self):
        probes = re.findall(
            r"^check_http_code byparr (.+)$", SCRIPT.read_text(), re.MULTILINE
        )
        self.assertEqual(probes, ["http://127.0.0.1:8191/ready 200"])

    def test_existing_backup_and_lock_contracts_are_retained(self):
        source = SCRIPT.read_text()
        self.assertIn("exec 9>/var/lock/update-minipc-leftover-services.lock", source)
        self.assertIn("flock -n 9", source)
        self.assertIn(
            'backup_copy_file /opt/byparr/compose.yaml "$BACKUP_DIR/byparr/compose.yaml"',
            source,
        )
        self.assertIn("require_container_running", source)
        self.assertIn("backup_keep_latest_dir_only", source)


if __name__ == "__main__":
    unittest.main()
