"""Real MaxMind-reader regressions for truncated and interrupted GeoIP updates."""

import errno
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# These tests deliberately run with stdlib unittest in the production image,
# without adding pytest or any application dependency to the qualified runtime.
# ruff: noqa: PT009,PT027
import maxminddb
from invisible_core import _geoip_db as geoip

FIXTURE = Path(__file__).parent / "fixtures/geoip/GeoIP2-City-Test.mmdb"
OLD = "2026.10.07"
NEW = "2026.10.14"


class GeoIPCacheTests(unittest.TestCase):
    """Exercise the installed loader using a real valid database and truncations."""

    def setUp(self):
        """Use a disposable cache with no live network or environment mutations."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "geoip"
        self.root.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(geoip, "_geoip_root", return_value=self.root).start()
        patch.object(geoip, "_resolve_latest_geoip_tag", return_value=NEW).start()
        patch.object(
            geoip,
            "_download_file",
            side_effect=lambda _url, target: target.write_bytes(b"archive"),
        ).start()
        patch.dict(os.environ, {}, clear=False).start()
        os.environ.pop("STEALTHFOX_GEOIP_MMDB", None)
        self.old = self.write(OLD, FIXTURE.read_bytes())

    def write(self, tag, data):
        """Install a test cache entry with ordinary production naming."""
        path = self.root / tag / geoip.GEOIP_MMDB_NAME
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        return path

    def test_newest_truncated_file_never_replaces_valid_cached_selection(self):
        """Reproduce the production valid-old plus truncated-new cache state."""
        self.write(NEW, FIXTURE.read_bytes()[:1000])
        self.assertEqual(geoip.geoip_mmdb_path(), self.old)
        with patch.object(geoip, "_resolve_latest_geoip_tag", return_value=None):
            self.assertEqual(geoip.ensure_geoip_mmdb(), self.old)

    def test_enospc_during_refresh_keeps_a_valid_cache_for_later_calls(self):
        """Failure cannot leave a partial target that the next launch trusts."""
        observed = []

        def fail_extract(_archive, destination) -> None:
            (destination / geoip.GEOIP_MMDB_NAME).write_bytes(
                FIXTURE.read_bytes()[:1000]
            )
            observed.append(geoip.geoip_mmdb_path())
            raise OSError(errno.ENOSPC, "controlled cache full")

        with patch.object(geoip, "_extract", side_effect=fail_extract):
            self.assertEqual(geoip.ensure_geoip_mmdb(), self.old)
        self.assertEqual(observed, [self.old])
        self.assertEqual(geoip.geoip_mmdb_path(), self.old)
        self.assertFalse((self.root / NEW / geoip.GEOIP_MMDB_NAME).exists())
        self.assertFalse(list(self.root.glob(".geoip-*")))

    def test_success_is_published_only_after_a_real_reader_accepts_it(self):
        """Readers keep seeing old data until a complete new database is ready."""
        observed = []

        def extract(_archive, destination) -> None:
            target = destination / geoip.GEOIP_MMDB_NAME
            target.write_bytes(FIXTURE.read_bytes()[:1000])
            observed.append(geoip.geoip_mmdb_path())
            shutil.copyfile(FIXTURE, target)
            observed.append(geoip.geoip_mmdb_path())

        with patch.object(geoip, "_extract", side_effect=extract):
            actual = geoip.ensure_geoip_mmdb()
        self.assertEqual(observed, [self.old, self.old])
        self.assertEqual(actual, self.root / NEW / geoip.GEOIP_MMDB_NAME)
        with maxminddb.open_database(str(actual)) as reader:
            self.assertEqual(reader.metadata().database_type, "GeoIP2-City")
        self.assertFalse(self.old.exists())
        self.assertFalse(list(self.root.glob(".geoip-*")))

    def test_invalid_download_and_explicit_override_are_not_accepted(self):
        """Syntactically invalid data never becomes a selectable database."""

        def extract(_archive, destination) -> None:
            (destination / geoip.GEOIP_MMDB_NAME).write_bytes(b"not an mmdb")

        with patch.object(geoip, "_extract", side_effect=extract):
            self.assertEqual(geoip.ensure_geoip_mmdb(), self.old)
        invalid = self.write("override", b"bad")
        with (
            patch.dict(os.environ, {"STEALTHFOX_GEOIP_MMDB": str(invalid)}),
            self.assertRaises(RuntimeError),
        ):
            geoip.ensure_geoip_mmdb()

    def test_invalid_only_cache_is_not_a_successful_offline_fallback(self):
        """Cold/invalid offline state must fail clearly instead of poisoning launch."""
        self.old.write_bytes(b"truncated")
        with (
            patch.object(geoip, "_resolve_latest_geoip_tag", return_value=None),
            self.assertRaises(RuntimeError),
        ):
            geoip.ensure_geoip_mmdb()


if __name__ == "__main__":
    unittest.main()
