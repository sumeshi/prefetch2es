"""Bundle libscca and application sources for standalone releases."""

import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
from urllib.request import urlopen


def prepare(output: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    package = next(p for p in lock["package"] if p["name"] == "libscca-python")
    source = package["sdist"]
    with urlopen(source["url"], timeout=60) as response:
        data = response.read()
    if "sha256:" + hashlib.sha256(data).hexdigest() != source["hash"]:
        raise RuntimeError("libscca source checksum does not match uv.lock")

    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"libscca_python-{package['version']}.tar.gz"
    archive.write_bytes(data)
    # Build the actual bundled library from the source supplied to recipients.
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            sys.executable,
            "--reinstall",
            "--no-deps",
            str(archive.resolve()),
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "archive",
            "--format=tar.gz",
            "--prefix=prefetch2es/",
            f"--output={(output / 'prefetch2es-source.tar.gz').resolve()}",
            "HEAD",
        ],
        cwd=root,
        check=True,
    )
    shutil.copyfile(root / "REBUILD.md", output / "REBUILD.md")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    prepare(parser.parse_args().output)
