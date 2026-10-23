"""Native-parser fixture shared by binary and Elasticsearch validation.

Windows 10 CALC Prefetch fixture from EricZimmerman/Prefetch (original MD5 40b8917687c2b1cf8ac5bfeea6476a39), stored unchanged.
Source: https://github.com/EricZimmerman/Prefetch/blob/841212266356a9121a1c34ee538cbce2bb2b9cf3/Prefetch.Test/TestFiles/Win10/CALC.EXE-3FBEF7FD.pf
"""

from hashlib import sha256
from pathlib import Path

PACKAGE = "prefetch2es"
JSON_COMMAND = "prefetch2json"
TIMELINE_MODES = (False, True)
SUPPORTS_MULTIPROCESSING = True
API_KWARGS = {}
CLI_ARGS = ()


def create_artifact(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    payload = (Path(__file__).with_name("fixtures") / "calc-win10.bin").read_bytes()
    if (
        sha256(payload).hexdigest()
        != "e1d11876560511788c58e957d302a4a953e8cd8e8d7c0290796393058c164319"
    ):
        raise RuntimeError("Native validation fixture checksum mismatch")
    destination = directory / "CALC.EXE-3FBEF7FD.pf"
    destination.write_bytes(payload)
    return destination
