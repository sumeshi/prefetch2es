# prefetch2es
[![MIT License](http://img.shields.io/badge/license-MIT-blue.svg?style=flat)](LICENSE)
[![PyPI version](https://badge.fury.io/py/prefetch2es.svg)](https://badge.fury.io/py/prefetch2es)
[![Python Versions](https://img.shields.io/pypi/pyversions/prefetch2es.svg)](https://pypi.org/project/prefetch2es/)
[![DockerHub Status](https://shields.io/docker/cloud/build/sumeshi/prefetch2es)](https://hub.docker.com/r/sumeshi/prefetch2es)

![prefetch2es logo](https://gist.githubusercontent.com/sumeshi/c2f430d352ae763273faadf9616a29e5/raw/fd3921cb75a484af98d795f194e9e4cb16b88515/prefetch2es.svg)

Fast import of Windows Prefetch(.pf) into Elasticsearch.

prefetch2es uses C library [libscca](https://github.com/libyal/libscca).

## Usage

When using from the commandline interface:

```bash
$ prefetch2es /path/to/your/file.pf
```

When using from the python-script:

```python
from prefetch2es.prefetch2es import prefetch2es

if __name__ == '__main__':
    filepath = '/path/to/your/file.pf'
    prefetch2es(filepath)
```

## Arguments
prefetch2es supports importing from multiple files.

```
$ prefetch2es file1.pf file2.pf file3.pf
```

Also, possible to import recursively from a specific directory.

```
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

$ prefetch2es /pffiles/ # The Path is recursively expanded to file1~6.pf.
```

### Options
```
--host: 
    ElasticSearch host address
    (default: localhost)

--port: 
    ElasticSearch port number
    (default: 9200)

--index: 
    Index name
    (default: prefetch2es)

--scheme:
  Scheme to use (http, or https)
  (default: http)

--pipeline
  Elasticsearch Ingest Pipeline to use
  (default: )

--login:
  The login to use if Elastic Security is enable
  (default: )

--pwd:
  The password linked to the login provided
  (default: )

```

## Examples

When using from the commandline interface:

```
$ prefetch2es /path/to/your/file.pf --host=localhost --port=9200 --index=foobar
```

When using from the python-script:

```python
if __name__ == '__main__':
    prefetch2es('/path/to/your/file.pf', host=localhost, port=9200, index='foobar')
```

With the Amazon Elasticsearch Serivce (ES):

```
$ prefetch2es /path/to/your/file.pf --host=example.us-east-1.es.amazonaws.com --port=443 --scheme=https --index=foobar
```

With credentials for Elastic Security:

```
$ prefetch2es /path/to/your/file.pf --host=localhost --port=9200 --index=foobar --login=elastic --pwd=******
```

Note: The current version does not verify the certificate.

## Supported Prefetch versions

- Windows XP
- Windows 2003
- Windows Vista (SP0)
- Windows 7 (SP0)
- Windows 8.1
- Windows 10 1809
- Windows 10 1903

For more information, please visit [libscca](https://github.com/libyal/libscca).

## Appendix
### prefetch2json
Extra feature. 🍣 🍣 🍣

Convert from Windows Prefetch to json file.

```
$ prefetch2json /path/to/your/file.pf /path/to/output/target.json
```

Convert from Windows Prefetch to Python dict object.

```python
from prefetch2es import prefetch2json

if __name__ == '__main__':
  filepath = '/path/to/your/file.pf'
  result: dict = prefetch2json(filepath)
```

## Output Format Example
Using the sample prefetch file of [EricZimmerman/Prefetch](https://github.com/EricZimmerman/Prefetch) as an example.

```
{
  "name": "CALC.EXE",
  "filenames": [
    "\\DEVICE\\HARDDISKVOLUME2\\WINDOWS\\SYSTEM32\\NTDLL.DLL",
    ...
  ],
  "exec_count": 2,
  "last_exec_time": 130974496211967500,
  "format_version": 23,
  "prefetch_hash": 2013131135,
  "metrics": [
    {
      "filename": "\\DEVICE\\HARDDISKVOLUME2\\WINDOWS\\SYSTEM32\\NTDLL.DLL",
      "file_reference": 281474976736310
    },
    ...
  ],
  "volumes": [
    {
      "path": "\\DEVICE\\HARDDISKVOLUME2",
      "creation_time": 130974525181093750,
      "serial_number": 2281737263
    }
  ]
}
```

## Installation

### via PyPI
```
$ pip install prefetch2es
```

### via DockerHub
```
$ docker pull sumeshi/prefetch2es:latest
```

## Run with Docker
https://hub.docker.com/r/sumeshi/prefetch2es


## prefetch2es
```bash
# "host.docker.internal" is only available in mac and windows environments.
# For linux, use the --add-host option.
$ docker run -t --rm -v $(pwd):/app sumeshi/prefetch2es:latest prefetch2es SAMPLE.pf --host=host.docker.internal
```

## prefetch2json
```bash
$ docker run -t --rm -v $(pwd):/app sumeshi/prefetch2es:latest prefetch2es SAMPLE.pf out.json
```

Do not use the "latest" image if at all possible.  
The "latest" image is not a released version, but is built from the contents of the master branch.

## Contributing

[CONTRIBUTING](https://github.com/sumeshi/prefetch2es/blob/master/CONTRIBUTING)

The source code for prefetch2es is hosted at GitHub, and you may download, fork, and review it from this repository(https://github.com/sumeshi/prefetch2es).
Please report issues and feature requests. :sushi: :sushi: :sushi:

## License
prefetch2es is released under the [MIT](https://github.com/sumeshi/prefetch2es/blob/master/LICENSE) License.

Powered by [libscca](https://github.com/libyal/libscca).