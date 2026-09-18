# prefetch2es
[![MIT License](http://img.shields.io/badge/license-MIT-blue.svg?style=flat)](LICENSE)
[![PyPI version](https://badge.fury.io/py/prefetch2es.svg)](https://badge.fury.io/py/prefetch2es)
[![pytest](https://github.com/sumeshi/prefetch2es/actions/workflows/test.yaml/badge.svg)](https://github.com/sumeshi/prefetch2es/actions/workflows/test.yaml)

![prefetch2es logo](https://gist.githubusercontent.com/sumeshi/c2f430d352ae763273faadf9616a29e5/raw/fd3921cb75a484af98d795f194e9e4cb16b88515/prefetch2es.svg)

A command-line tool for parsing Windows Prefetch files and importing the results into Elasticsearch.

**prefetch2es** is built on [pyscca](https://github.com/libyal/libscca/tree/main/pyscca) and converts Windows Prefetch artifacts into Elasticsearch-friendly records.

## Features

- Parse Windows Prefetch (`.pf`) files using pyscca
- Process a single file, multiple files, or a directory of `.pf` files
- Import parsed records into Elasticsearch (`prefetch2es`)
- Export parsed records as JSON or JSONL (`prefetch2json`)
- Generate timeline-oriented records for forensic analysis (`--timeline`)


## Installation

### From PyPI

```bash
$ pip install prefetch2es
```

### From GitHub Releases

Standalone binaries built with Nuitka are available from GitHub Releases.

```bash
$ chmod +x ./prefetch2es
$ ./prefetch2es {{options...}}
```

```powershell
> prefetch2es.exe {{options...}}
```


## Usage

**prefetch2es** can be executed from the command line or incorporated into a Python script.

```bash
$ prefetch2es /path/to/your/file.pf
```

```python
from prefetch2es import prefetch2es
prefetch2es("/path/to/your/file.pf")
```

### Arguments

prefetch2es can process multiple files at once.

```bash
$ prefetch2es file1.pf file2.pf file3.pf
```

prefetch2es can recursively process all `.pf` files under a specified directory.

```bash
$ tree .
pffiles/
  ├── file1.pf
  ├── file2.pf
  ├── file3.pf
  └── subdirectory/
    ├── file4.pf
    └── subsubdirectory/
      ├── file5.pf
      └── file6.pf

$ prefetch2es /pffiles/ # The path is recursively expanded to all .pf files.
```

### Options

```
--version, -v

--help, -h

--quiet, -q
  Suppress standard output
  (default: False)

--multiprocess, -m:
  Enable multiprocessing for faster processing.
  (default: False)

--size:
  Number of files to process per chunk (default: 500)

--host:
  Elasticsearch host address (default: localhost)

--port:
  Elasticsearch port number (default: 9200)

--index:
  Destination index name (default: prefetch2es)

--scheme:
  Protocol scheme to use (http or https) (default: http)

--pipeline:
  Elasticsearch ingest pipeline to use (default: )

--timeline:
  Enable timeline analysis mode for forensic investigation
  (default: False)

--tags:
  Comma-separated tags to add to each record for identification
  (e.g., hostname, domain name) (default: )

--login:
  Username for Elasticsearch authentication

--pwd:
  Password for Elasticsearch authentication

--no-verify-certs:
  Disable TLS certificate verification (default: False)

--ca-certs:
  Path to a CA certificate bundle for TLS verification (default: None)
```

### Examples

When using from the command line:

```bash
$ prefetch2es /path/to/your/file.pf --host=localhost --port=9200 --index=foobar --size=500
```

When using from a Python script:

```python
if __name__ == '__main__':
    prefetch2es('/path/to/your/file.pf', host='localhost', port=9200, index='foobar', size=500)
```

With Elasticsearch authentication:

```bash
$ prefetch2es /path/to/your/file.pf --host=localhost --port=9200 --index=foobar --login=elastic --pwd=******
```

With timeline analysis mode:

```bash
$ prefetch2es /path/to/your/file.pf --timeline --index=prefetch-timeline
```

With custom tags for system identification:

```bash
# Single tag
$ prefetch2es /path/to/your/file.pf --timeline --tags="WORKSTATION-01" --index=prefetch-timeline

# Multiple tags (comma-separated)
$ prefetch2es /path/to/your/file.pf --timeline --tags="WORKSTATION-01,FOO,BAR" --index=prefetch-timeline
```

> [!WARNING]
> TLS certificate verification is enabled by default. Use `--no-verify-certs` only
> when connecting to a trusted cluster with a self-signed or otherwise
> unverifiable certificate. Use `--ca-certs /path/to/ca.pem` to provide a
> private CA bundle while keeping verification enabled.

## Appendix

### prefetch2json

`prefetch2json` converts Windows Prefetch files to JSON.

```bash
$ prefetch2json /path/to/your/file.pf -o /path/to/output/target.json
```

`prefetch2json` also supports line-delimited output. `--format jsonl` (or
`ndjson`) writes one record per line without holding the entire dataset in
memory. When no output path is specified, the default extension is `.jsonl`:

```bash
$ prefetch2json /path/to/your/file.pf --format jsonl
```

You can also convert Windows Prefetch files directly into a Python `list[dict]`:

```python
from prefetch2es import prefetch2json

if __name__ == '__main__':
    filepath = '/path/to/your/file.pf'
    result: list[dict] = prefetch2json(filepath)
```

With timeline analysis and custom tags:

```bash
$ prefetch2json /path/to/your/file.pf --timeline --tags="WORKSTATION-01,FINANCE" -o output.json
```

### Timeline Analysis

prefetch2es supports timeline analysis mode that creates specialized timeline records for forensic investigation.

Standard mode creates one record per Prefetch file.
Timeline mode creates one record per recorded execution timestamp.

```bash
$ prefetch2es /path/to/your/file.pf --timeline --index=prefetch-timeline
```

This mode creates records optimized for temporal analysis of application execution patterns, making it easier to investigate system activity over time.

#### Tags for System Identification

Use the `--tags` option to add custom tags for better organization and filtering:

```bash
# Identify source system and department
$ prefetch2es /path/to/prefetch/ --timeline --tags="WORKSTATION-01" --index=prefetch-timeline

# Add criticality level
$ prefetch2es /path/to/prefetch/ --timeline --tags="SERVER-02,FOO,BAR" --index=prefetch-timeline
```

## Output Format Examples

### Standard Mode

```json
[
  {
    "name": "CMD.EXE",
    "filenames": [
      "\\VOLUME{01d1217a9c4c6779-8c9f49ec}\\WINDOWS\\SYSTEM32\\DISKPART.EXE",
      "\\VOLUME{01d12173f395296c-66f451bc}\\CMDER129\\VENDOR\\CLINK\\CLINK_DLL_X64.DLL",
      "\\VOLUME{01d1217a9c4c6779-8c9f49ec}\\WINDOWS\\SYSTEM32\\NTDLL.DLL",
      "\\VOLUME{01d1217a9c4c6779-8c9f49ec}\\WINDOWS\\SYSTEM32\\CMD.EXE",
      ...
    ],
    "exec_count": 55,
    "last_exec_times": [
      "2016-01-12T20:07:03.981069Z",
      "2016-01-10T02:29:02.788726Z",
      "2016-01-04T23:27:28.405869Z",
      "2016-01-04T23:27:28.726891Z",
      "2016-01-04T18:38:10.935655Z",
      "2016-01-04T18:38:11.344163Z",
      "2015-12-31T21:42:29.667018Z",
      "2015-12-17T22:34:21.579861Z"
    ],
    "format_version": 30,
    "prefetch_hash": "D269B812",
    "number_of_volumes": 2,
    "number_of_filenames": 62,
    "number_of_file_metrics_entries": 62,
    "metrics": [
      {
        "filename": "\\VOLUME{01d1217a9c4c6779-8c9f49ec}\\WINDOWS\\SYSTEM32\\DISKPART.EXE",
        "file_reference": "0X1000000009EF4"
      },
      {
        "filename": "\\VOLUME{01d12173f395296c-66f451bc}\\CMDER129\\VENDOR\\CLINK\\CLINK_DLL_X64.DLL",
        "file_reference": "0X100000000B5A6"
      },
      {
        "filename": "\\VOLUME{01d1217a9c4c6779-8c9f49ec}\\WINDOWS\\SYSTEM32\\NTDLL.DLL",
        "file_reference": "0X10000000575F4"
      },
      {
        "filename": "\\VOLUME{01d1217a9c4c6779-8c9f49ec}\\WINDOWS\\SYSTEM32\\CMD.EXE",
        "file_reference": "0X1000000009CA8"
      },
      ...
    ],
    "volumes": [
      {
        "path": "\\VOLUME{01d12173f395296c-66f451bc}",
        "creation_time": "2015-11-17T20:10:06.204964Z",
        "serial_number": "66F451BC"
      },
      {
        "path": "\\VOLUME{01d1217a9c4c6779-8c9f49ec}",
        "creation_time": "2015-11-17T20:57:46.243468Z",
        "serial_number": "8C9F49EC"
      }
    ],
    "source_file": "/workspace/tests/cache/CMD.EXE-D269B812.pf",
    "tags": [
      "prefetch"
    ]
  },
  ...
]
```

### Timeline Mode

```json
[
  {
    "@timestamp": "2016-01-12T20:07:03.981069Z",
    "event": {
      "action": "prefetch-executed",
      "category": [
        "process"
      ],
      "type": [
        "start"
      ],
      "kind": "event",
      "provider": "prefetch",
      "module": "windows",
      "dataset": "windows.prefetch"
    },
    "process": {
      "name": "CMD.EXE",
      "start": "2016-01-12T20:07:03.981069Z"
    },
    "windows": {
      "prefetch": {
        "exec_count": 55,
        "hash": {
          "prefetch": "D269B812"
        },
        "format_version": 30,
        "volumes": [
          {
            "path": "\\VOLUME{01d12173f395296c-66f451bc}",
            "creation_time": "2015-11-17T20:10:06.204964Z",
            "serial_number": "66F451BC"
          },
          {
            "path": "\\VOLUME{01d1217a9c4c6779-8c9f49ec}",
            "creation_time": "2015-11-17T20:57:46.243468Z",
            "serial_number": "8C9F49EC"
          }
        ],
        "metrics": [
          {
            "filename": "\\VOLUME{01d1217a9c4c6779-8c9f49ec}\\WINDOWS\\SYSTEM32\\DISKPART.EXE",
            "file_reference": "0X1000000009EF4"
          },
          {
            "filename": "\\VOLUME{01d12173f395296c-66f451bc}\\CMDER129\\VENDOR\\CLINK\\CLINK_DLL_X64.DLL",
            "file_reference": "0X100000000B5A6"
          },
          {
            "filename": "\\VOLUME{01d1217a9c4c6779-8c9f49ec}\\WINDOWS\\SYSTEM32\\NTDLL.DLL",
            "file_reference": "0X10000000575F4"
          },
          {
            "filename": "\\VOLUME{01d1217a9c4c6779-8c9f49ec}\\WINDOWS\\SYSTEM32\\CMD.EXE",
            "file_reference": "0X1000000009CA8"
          },
          ...
        ]
      }
    },
    "log": {
      "file": {
        "path": "/workspace/tests/cache/CMD.EXE-D269B812.pf"
      }
    },
    "tags": [
      "prefetch"
    ]
  },
  ...
]
```

## Supported Prefetch versions

- Windows XP
- Windows 2003
- Windows Vista (SP0)
- Windows 7 (SP0)
- Windows 8.1
- Windows 10 1809
- Windows 10 1903
- Windows 11 24H2

For more information, please visit [libscca](https://github.com/libyal/libscca/blob/main/documentation/Windows%20Prefetch%20File%20(PF)%20format.asciidoc).

## Contributing

The source code for prefetch2es is hosted on GitHub. You can download, fork, and review it from this repository: https://github.com/sumeshi/prefetch2es.
Please report issues and feature requests. :sushi: :sushi: :sushi:

## License

prefetch2es is released under the [MIT](https://github.com/sumeshi/prefetch2es/blob/master/LICENSE) License.

### Third-party licenses

Standalone releases are ZIP archives containing both commands and `LICENSES.txt`
with project, runtime dependency and Python license notices. Keep the notices
with the executables when redistributing them.

The ZIP also contains the libscca source used for the build and the application
release source under `sources/`. See [REBUILD.md](REBUILD.md) to rebuild with a
modified libscca. Embedded native dependencies still require separate review.

The standalone binaries distributed via GitHub Releases bundle [libscca / pyscca](https://github.com/libyal/libscca),
which is licensed under the [GNU Lesser General Public License v3.0 or later (LGPL-3.0-or-later)](https://www.gnu.org/licenses/lgpl-3.0.html).

- Upstream source: https://github.com/libyal/libscca
- Bundled version: [`libscca-python==20260527`](https://pypi.org/project/libscca-python/20260527/) (source: https://github.com/libyal/libscca/releases/tag/20260527)
- License text: https://github.com/libyal/libscca/blob/main/COPYING.LESSER

You may obtain, modify, and rebuild libscca from the upstream source above in accordance with the LGPL.
