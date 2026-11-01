"""Validate and atomically publish GeoIP updates in the pinned invisible-core."""

from pathlib import Path


def patch_source(source: str) -> str:
    """Require the reviewed loader anchors before changing its cache lifecycle."""
    changes = [
        (
            "import requests\n",
            "import requests\nimport maxminddb\n",
        ),
        (
            "def _cached_geoip_mmdb() -> Path | None:\n",
            '''def _valid_geoip_mmdb(path: Path) -> bool:
    """Only complete, readable MaxMind databases can be published or selected."""
    try:
        with maxminddb.open_database(str(path)) as reader:
            reader.metadata()
        return True
    except (OSError, maxminddb.InvalidDatabaseError):
        return False


def _cached_geoip_mmdb() -> Path | None:
''',
        ),
        (
            '    cands = sorted(root.glob("*/*.mmdb"))\n    return cands[-1] if cands else None\n',
            """    cands = sorted(root.glob("*/*.mmdb"), reverse=True)
    return next((p for p in cands
                 if not p.parent.name.startswith(".") and _valid_geoip_mmdb(p)), None)
""",
        ),
        (
            """    if not target.exists():
        url = GEOIP_RELEASE_URL_TEMPLATE.format(tag=tag, asset=GEOIP_ASSET)
        dst_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / GEOIP_ASSET
            _download_file(url, archive)
            _extract(archive, dst_dir)
    if target.exists():
        return target
    # asset name inside the zip may differ from GEOIP_MMDB_NAME
    found = sorted(dst_dir.glob("*.mmdb"))
    if found:
        return found[0]
    raise RuntimeError(f"geoip mmdb not found after extraction in {dst_dir}")
""",
            """    if _valid_geoip_mmdb(target):
        return target
    url = GEOIP_RELEASE_URL_TEMPLATE.format(tag=tag, asset=GEOIP_ASSET)
    root = _geoip_root()
    root.mkdir(parents=True, exist_ok=True)
    # The archive uses /tmp; only old+new database bytes consume the GeoIP budget.
    # Staging shares the target filesystem, making os.replace an atomic publish.
    with tempfile.TemporaryDirectory() as download_dir, tempfile.TemporaryDirectory(
        prefix=".geoip-", dir=root
    ) as staging_dir:
        archive = Path(download_dir) / GEOIP_ASSET
        _download_file(url, archive)
        staging = Path(staging_dir)
        _extract(archive, staging)
        extracted = staging / GEOIP_MMDB_NAME
        if not extracted.exists():
            found = sorted(staging.glob("*.mmdb"))
            if not found:
                raise RuntimeError("GeoIP archive contains no database")
            extracted = found[0]
        if not _valid_geoip_mmdb(extracted):
            raise RuntimeError("Downloaded GeoIP database is invalid; cache unchanged")
        dst_dir.mkdir(parents=True, exist_ok=True)
        os.replace(extracted, target)
    return target
""",
        ),
        (
            """        if not p.exists():
            raise RuntimeError(f"STEALTHFOX_GEOIP_MMDB points to a missing file: {p}")
        return p
""",
            """        if not _valid_geoip_mmdb(p):
            raise RuntimeError(f"STEALTHFOX_GEOIP_MMDB is missing or invalid: {p}")
        return p
""",
        ),
    ]
    for before, after in changes:
        if source.count(before) != 1:
            message = (
                "Pinned GeoIP loader changed; review atomic cache patch before building"
            )
            raise RuntimeError(message)
        source = source.replace(before, after)
    return source


def main() -> None:
    """Patch the installed loader only during the reviewed image build."""
    import invisible_core._geoip_db as geoip  # noqa: PLC0415

    target = Path(geoip.__file__)
    target.write_text(patch_source(target.read_text()))
    print("Applied validated atomic GeoIP cache update")  # noqa: T201


if __name__ == "__main__":
    main()
