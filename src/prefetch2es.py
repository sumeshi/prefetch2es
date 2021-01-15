# coding: utf-8
import argparse
import traceback
from pathlib import Path
from typing import List, Generator
from hashlib import sha1

import pyscca
import orjson
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk


class ElasticsearchUtils(object):
    def __init__(self, hostname: str, port: int, scheme: str, login: str, pwd: str):
        if login == "":
            self.es = Elasticsearch(host=hostname, port=port, scheme=scheme)
        else:
            self.es = Elasticsearch(host=hostname, port=port, scheme=scheme, verify_certs=False, http_auth=(login, pwd))

    def calc_hash(self, record: dict) -> str:
        """Calculate hash value from record.
        Args:
            record (dict): Prefetch record.
        Returns:
            str: Hash value
        """
        return sha1(orjson.dumps(record, option=orjson.OPT_SORT_KEYS)).hexdigest()

    def bulk_indice(self, record: dict, index_name: str) -> None:
        """Bulk indices the documents into Elasticsearch.
        Args:
            record (dict): Dictionary of record read from prefetch files.
            index_name (str): Target Elasticsearch Index.
        """
        bulk(
            self.es,
            [{"_id": self.calc_hash(record), "_index": index_name, "_source": record}],
            raise_on_error=False,
        )


class Prefetch2es(object):
    def __init__(self, filepath: str) -> None:
        self.path = Path(filepath)

    def to_dict(self) -> dict:
        p = pyscca.file()
        p.open_file_object(self.path.open(mode='rb'))

        result = {
            'name': p.executable_filename,
            'filenames': [name for name in p.filenames],
            'exec_count': p.run_count,
            'last_exec_time': p.get_last_run_time_as_integer(0),
            'format_version': p.format_version,
            'prefetch_hash': p.prefetch_hash,
            'metrics': [
                {
                    'filename': metrics.filename,
                    'file_reference': metrics.file_reference,
                } for metrics in p.file_metrics_entries
            ],
            'volumes': [
                {
                    'path': volume.device_path,
                    'creation_time': volume.get_creation_time_as_integer(),
                    'serial_number': volume.serial_number,
                } for volume in p.volumes
            ],
        }

        p.close()

        return result


def prefetch2es(
    filepath: str,
    host: str = "localhost",
    port: int = 9200,
    index: str = "prefetch2es",
    scheme: str = "http",
    login: str = "",
    pwd: str = ""
):
    """Fast import of Windows Prefetch(.pf) into Elasticsearch.
    Args:
        filepath (str):
            Windows Prefetch to import into Elasticsearch.
        host (str, optional):
            Elasticsearch host address. Defaults to "localhost".
        port (int, optional):
            Elasticsearch port number. Defaults to 9200.
        index (str, optional):
            Name of the index to create. Defaults to "prefetch2es".
        scheme (str, optional):
            Elasticsearch address scheme. Defaults to "http".
        login (str,optional):
            Elasticsearch login to connect into.
        pwd (str,optional):
            Elasticsearch password associated with the login provided.
    """
    es = ElasticsearchUtils(hostname=host, port=port, scheme=scheme, login=login, pwd=pwd)

    r = Prefetch2es(filepath)
    try:
        es.bulk_indice(r.to_dict(), index)
    except Exception:
        traceback.print_exc()


def prefetch2json(filepath: str) -> dict:
    """Convert prefetch to json.
    Args:
        filepath (str): Input Prefetch(.pf) file.
    Note:
        Since the content of the file is loaded into memory at once,
        it requires the same amount of memory as the file to be loaded.
    """
    r = Prefetch2es(filepath)
    buffer: dict = r.to_dict()
    return buffer


def console_prefetch2es():
    """ This function is loaded when used from the console.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "prefetchfiles",
        nargs="+",
        type=Path,
        help="Windows Prefetch files or directories containing them.",
    )

    # Options
    parser.add_argument("--host", default="localhost", help="Elasticsearch host")
    parser.add_argument("--port", default=9200, help="Elasticsearch port number")
    parser.add_argument("--index", default="prefetch2es", help="Index name")
    parser.add_argument("--scheme", default="http", help="Scheme to use (http, https)")
    parser.add_argument("--login", default="elastic", help="Login to use to connect to Elastic database")
    parser.add_argument("--pwd", default="", help="Password associated with the login")
    args = parser.parse_args()

    # Target files
    prefetchfiles = list()
    for prefetchfile in args.prefetchfiles:
        if prefetchfile.is_dir():
            prefetchfiles.extend(prefetchfile.glob("**/*.pf"))
            # prefetchfiles.extend(prefetchfile.glob("**/*.PF"))
        else:
            prefetchfiles.append(prefetchfile)

    # Indexing prefetch files
    for prefetchfile in prefetchfiles:
        print(f"Currently Importing {prefetchfile}")
        prefetch2es(
            filepath=prefetchfile,
            host=args.host,
            port=int(args.port),
            index=args.index,
            scheme=args.scheme,
            login=args.login,
            pwd=args.pwd
        )

    print("Import completed.\n")


def console_prefetch2json():
    """ This function is loaded when used from the console.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("prefetchfile", type=Path, help="Windows Prefetch file.")
    parser.add_argument("jsonfile", type=Path, help="Output json file path.")
    args = parser.parse_args()

    # Convert prefetch to json file.
    print(f"Converting {args.prefetchfile}")
    o = Path(args.jsonfile)
    o.write_text(
        orjson.dumps(
            prefetch2json(filepath=args.prefetchfile),
            option=orjson.OPT_INDENT_2
        ).decode('utf-8')
    )

    print("Convert completed.")


if __name__ == '__main__':
    console_prefetch2es()
