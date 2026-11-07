"""Copy new game data versions from the upstream mirrors into this repo.

Reads each upstream `metadata.json`, downloads every version this mirror
doesn't have yet, checks it's a readable .tar.xz archive, uploads it to the
`data` release, and rewrites `metadata.json` to point at the release files.
Versions are never removed, so the mirror keeps them if upstream drops them.

Run by .github/workflows/sync.yml. Locally: `python sync.py --dry-run`.
Needs only the standard library, plus the `gh` CLI for uploading.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

UPSTREAMS = [
    "https://git.battlecatsmodding.org/fieryhenry/BCData/raw/branch/main/metadata.json",
    "https://gitlab.com/fieryhenry/bcdata/-/raw/main/metadata.json",
]
TAG = "data"
METADATA = Path("metadata.json")
REGIONS = {"en", "jp", "kr", "tw"}
VERSION = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{1,2}$")
MAX_SIZE = 200 * 1024 * 1024  # far above any real archive (they're ~1-3 MB)
USER_AGENT = "bcdata-mirror"


def fetch(url: str, limit: int = MAX_SIZE) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{url} is larger than {limit} bytes")
    return data


def upstream_versions() -> dict[tuple[str, str], str]:
    """(region, version) -> download URL, from every upstream that answers."""
    found: dict[tuple[str, str], str] = {}
    for url in UPSTREAMS:
        try:
            meta = json.loads(fetch(url, 1024 * 1024))
            base = meta["base_url"]
            versions = meta["versions"]
        except Exception as e:  # one mirror being down is expected
            print(f"skipping {url}: {e}")
            continue
        for region, entries in versions.items():
            for version, path in entries.items():
                if region in REGIONS and VERSION.match(version):
                    found.setdefault((region, version), base + path)
    return found


def load_metadata(repo: str) -> dict[str, object]:
    if METADATA.exists():
        return json.loads(METADATA.read_text())
    return {
        "base_url": f"https://github.com/{repo}/releases/download/{TAG}/",
        "versions": {},
    }


def check_archive(path: Path) -> None:
    """Raise unless it's a .tar.xz with only plain, relative members."""
    with tarfile.open(path, "r:xz") as archive:
        for member in archive.getmembers():
            name = member.name
            if name.startswith("/") or ".." in Path(name).parts:
                raise ValueError(f"unsafe path in archive: {name}")
            if not (member.isfile() or member.isdir()):
                raise ValueError(f"unexpected member type in archive: {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="list, don't download")
    args = parser.parse_args()

    repo = os.environ.get("GITHUB_REPOSITORY", "meowzerskittycat/bcdata")
    metadata = load_metadata(repo)
    versions: dict[str, dict[str, str]] = metadata["versions"]  # type: ignore[assignment]

    missing = sorted(
        (key, url)
        for key, url in upstream_versions().items()
        if key[1] not in versions.get(key[0], {})
    )
    print(f"{len(missing)} new version(s)")
    if args.dry_run:
        for (region, version), url in missing:
            print(f"  {region} {version}  {url}")
        return 0

    failed = 0
    with tempfile.TemporaryDirectory() as tmp:
        for (region, version), url in missing:
            name = f"{region}-{version}.tar.xz"
            path = Path(tmp) / name
            try:
                path.write_bytes(fetch(url))
                check_archive(path)
                subprocess.run(
                    ["gh", "release", "upload", TAG, str(path), "--clobber"],
                    check=True,
                )
            except Exception as e:
                print(f"failed {region} {version}: {e}")
                failed += 1
                continue
            versions.setdefault(region, {})[version] = name
            print(f"added {region} {version}")

    for region in versions:
        versions[region] = dict(
            sorted(
                versions[region].items(),
                key=lambda kv: [int(p) for p in kv[0].split(".")],
            )
        )
    METADATA.write_text(json.dumps(metadata, indent=2) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
