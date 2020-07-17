# Prefetch2es
[![MIT License](http://img.shields.io/badge/license-MIT-blue.svg?style=flat)](LICENSE)
[![PyPI version](https://badge.fury.io/py/prefetch2es.svg)](https://badge.fury.io/py/prefetch2es)
[![Python Versions](https://img.shields.io/pypi/pyversions/prefetch2es.svg)](https://pypi.org/project/prefetch2es/)

Import Windows Prefetch(.pf) to Elasticsearch

prefetch2es uses Rust library [pyprefetch-rs](https://github.com/sumeshi/pyprefetch-rs).

```
Note: Nov 11, 2019
    Moved main development location to gitlab
```

## Usage
```bash
$ prefetch2es /path/to/your/file.pf
```

or

```python
from prefetch2es.prefetch2es import prefetch2es

if __name__ == '__main__':
    filepath = '/path/to/your/file.pf'
    prefetch2es(filepath)
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

--type: 
    Document-type name
    (default: prefetch2es)

```

### Examples
```
$ prefetch2es /path/to/your/file.pf --host=localhost --port=9200 --index=foo --type=bar
```

```py
if __name__ == '__main__':
    prefetch2es('/path/to/your/file.pf', host=localhost, port=9200, index='foo', type='bar')
```

## Installation
### via pip
```
$ pip install prefetch2es
```

The source code for prefetch2es is hosted at GitHub, and you may download, fork, and review it from this repository(https://github.com/sumeshi/prefetch2es).

Please report issues and feature requests. :sushi: :sushi: :sushi:

## License
prefetch2es is released under the [MIT](https://github.com/sumeshi/prefetch2es/blob/master/LICENSE) License.

Powered by [pyprefetch-rs](https://github.com/sumeshi/pyprefetch-rs).  