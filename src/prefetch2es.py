# coding: utf-8
import json
import argparse
import traceback
from pathlib import Path
from typing import List

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from tqdm import tqdm

from prefetch import Prefetch


class ElasticsearchUtils(object):
    def __init__(self, hostname: str, port: int) -> None:
        self.es = Elasticsearch(host=hostname, port=port)

    def bulk_indice(self, records, index_name: str) -> None:
        bulk(self.es, [
            {
                '_index': index_name,
                '_source': record
            } for record in records]
        )


class Prefetch2es(object):
    def __init__(self, filepath: str) -> None:
        self.path = Path(filepath)

    def get_json(self) -> dict:
        p = Prefetch(str(self.path.resolve()))

        result = {
            "name": p.name,
            "exec_count": p.exec_count,
            "last_exec_time": p.last_exec_time,
            "metrics": {
                metric.get('id'): metric for metric in p.get_metrics()
            },
            "volumes": {
                volume.get('id'): volume for volume in p.get_volumes()
            },
        }

        return result


def prefetch2es(filepath: str, host: str = 'localhost', port: int = 9200, index: str = 'prefetch2es'):
    es = ElasticsearchUtils(hostname=host, port=port)

    try:
        prefetch = Prefetch2es(filepath)
        result = [prefetch.get_json()]

        es.bulk_indice(result, index)
    except Exception:
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('prefetchfile', help='Windows Prefetch')
    parser.add_argument('--host', default='localhost', help='ElasticSearch host address')
    parser.add_argument('--port', default=9200, help='ElasticSearch port number')
    parser.add_argument('--index', default='prefetch2es', help='Index name')
    args = parser.parse_args()

    prefetch2es(
        filepath=args.prefetchfile,
        host=args.host,
        port=int(args.port),
        index=args.index,
    )


if __name__ == '__main__':
    main()
