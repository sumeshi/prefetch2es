"""Native-parser fixture shared by binary and Elasticsearch validation.

Windows 10 CALC Prefetch fixture from EricZimmerman/Prefetch (original MD5 40b8917687c2b1cf8ac5bfeea6476a39), stored unchanged.
Source: https://github.com/EricZimmerman/Prefetch/blob/841212266356a9121a1c34ee538cbce2bb2b9cf3/Prefetch.Test/TestFiles/Win10/CALC.EXE-3FBEF7FD.pf
"""

from hashlib import sha256
from pathlib import Path
import struct

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


def create_timestamp_artifact(
    directory: Path, timestamps, *, volume_timestamps=(130968655538095417,)
) -> Path:
    """A minimal uncompressed v30 file for native timestamp recovery checks."""
    directory.mkdir(parents=True, exist_ok=True)
    volume_timestamps = tuple(volume_timestamps)
    volume_data_size = 128 * len(volume_timestamps)
    payload = bytearray(384 + volume_data_size)
    struct.pack_into("<I4sII", payload, 0, 30, b"SCCA", 17, len(payload))
    payload[16:32] = "TEST.EXE".encode("utf-16le")
    # One metric, trace entry and filename; offsets follow the v30
    # file-information header and keep all referenced data inside the file.
    struct.pack_into(
        "<IIIIIIIII",
        payload,
        84,
        304,
        1,
        336,
        1,
        348,
        18,
        384,
        len(volume_timestamps),
        volume_data_size,
    )
    struct.pack_into("<II", payload, 316, 0, 8)
    payload[348:366] = "TEST.DLL\0".encode("utf-16le")
    path = "\\DEVICE\\VOLUME"
    for index, value in enumerate(volume_timestamps):
        path_offset = 96 * len(volume_timestamps) + 32 * index
        struct.pack_into(
            "<IIQI",
            payload,
            384 + 96 * index,
            path_offset,
            len(path),
            value,
            1234 + index,
        )
        offset = 384 + path_offset
        payload[offset : offset + len(path) * 2] = path.encode("utf-16le")
    for index, value in enumerate(timestamps):
        if index >= 8:
            raise ValueError("Prefetch supports at most eight timestamp slots")
        struct.pack_into("<Q", payload, 128 + index * 8, value)
    destination = directory / "timestamps.pf"
    destination.write_bytes(payload)
    return destination
