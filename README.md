# prefetch2es
[![LGPL-3.0 License](http://img.shields.io/badge/license-LGPL--3.0-blue.svg?style=flat)](LICENSE)
[![PyPI version](https://badge.fury.io/py/prefetch2es.svg)](https://badge.fury.io/py/prefetch2es)
[![pytest](https://github.com/sumeshi/prefetch2es/actions/workflows/test.yaml/badge.svg)](https://github.com/sumeshi/prefetch2es/actions/workflows/test.yaml)

![prefetch2es logo](https://gist.githubusercontent.com/sumeshi/c2f430d352ae763273faadf9616a29e5/raw/fd3921cb75a484af98d795f194e9e4cb16b88515/prefetch2es.svg)

A library for fast parse & import of Windows Prefetch into Elasticsearch.

**prefetch2es** uses the Python library [pyscca](https://github.com/libyal/libscca/tree/main/pyscca), providing high-performance parsing of Windows Prefetch files.

## Usage

**prefetch2es** can be executed from the command line or incorporated into a Python script.

```bash
$ prefetch2es /path/to/your/file.pf
```

```python
from prefetch2es import prefetch2es

if __name__ == '__main__':
    filepath = '/path/to/your/file.pf'
    prefetch2es(filepath)
```

### Arguments

prefetch2es supports simultaneous import of multiple files.

```bash
$ prefetch2es file1.pf file2.pf file3.pf
```

It also allows recursive import from the specified directory.

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
  Enable multiprocessing for faster execution
  (default: False)

--size:
  Chunk size for processing (default: 500)

--host:
  Elasticsearch host address (default: localhost)

--port:
  Elasticsearch port number (default: 9200)

--index:
  Destination index name (default: prefetch2es)

--scheme:
  Protocol scheme to use (http or https) (default: http)

--pipeline:
  Elasticsearch Ingest Pipeline to use (default: )

--timeline:
  Enable timeline analysis mode for forensic investigation
  (default: False)

--tags:
  Comma-separated tags to add to each record for identification
  (e.g., hostname, domain name) (default: )

--login:
  The login to use if Elastic Security is enabled (default: )

--pwd:
  The password associated with the provided login (default: )
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

With credentials for Elastic Security:

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

Note: The current version does not verify the certificate.

## Appendix

### prefetch2json

An additional feature: :sushi: :sushi: :sushi:

Convert Windows Prefetch to a JSON file.

```bash
$ prefetch2json /path/to/your/file.pf -o /path/to/output/target.json
```

Convert Windows Prefetch to a Python List[dict] object.

```python
from prefetch2es import prefetch2json

if __name__ == '__main__':
    filepath = '/path/to/your/file.pf'
    result: List[dict] = prefetch2json(filepath)
```

With timeline analysis and custom tags:

```bash
$ prefetch2json /path/to/your/file.pf --timeline --tags="WORKSTATION-01,FINANCE" -o output.json
```

### Timeline Analysis

prefetch2es supports timeline analysis mode that creates specialized timeline records for forensic investigation.

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

## Installation

### from PyPI

```bash
$ pip install prefetch2es
```

### from GitHub Releases

The version compiled into a binary using Nuitka is also available for use.

```bash
$ chmod +x ./prefetch2es
$ ./prefetch2es {{options...}}
```

```powershell
> prefetch2es.exe {{options...}}
```

Do not use the "latest" image if at all possible.  
The "latest" image is not a released version, but is built from the contents of the master branch.

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

prefetch2es is released under the [LGPL-3.0](https://github.com/sumeshi/prefetch2es/blob/master/LICENSE) License.

Powered by following libraries:
- [pyscca](https://github.com/libyal/libscca/tree/main/pyscca)
- [Nuitka](https://github.com/Nuitka/Nuitka)
