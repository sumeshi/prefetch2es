# coding: utf-8
import os
import json
import argparse
import traceback

from pathlib import Path
from typing import List, Generator
from subprocess import check_output

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from tqdm import tqdm


class ElasticsearchUtils(object):
    def __init__(self, hostname: str, port: int) -> None:
        self.es = Elasticsearch(host=hostname, port=port)

    def bulk_indice(self, records, index_name: str, type_name: str) -> None:
        bulk(self.es, [
            {
                '_index': index_name,
                '_type': type_name,
                '_source': record
            } for record in records]
        )


#class Prefetch2es(object):
#    def __init__(self, filepath: str) -> None:
#        self.path = Path(filepath)
#
#    def gen_json(self, size: int) -> Generator:
#        buffer: List[dict] = []
#
#        for record in self.parser.entries_json():
#            result = json.loads(record)
#
#            attributes = {}
#            for attribute in result.get('attributes'):
#                attributes[attribute.get('header').get('type_code')] = attribute
#
#            result['attributes'] = attributes
#
#            buffer.append(result)
#
#            if len(buffer) >= size:
#                yield buffer
#                buffer.clear()
#        else:
#            yield buffer


def prefetch2es(filepath: str, host: str = 'localhost', port: int = 9200, index: str = 'prefetch2es', type: str = 'prefetch2es', size: int = 500):

    # work in progress
    parent = Path(__file__).parent.parent
    check_output(f"python {parent}/analyzePF/apf.py parse csv summary -s {filepath} -t ./{Path(filepath).with_suffix('').name}.csv", shell=True)

    csv_lines = Path(f"{Path(filepath).with_suffix('')}.csv").read_text().splitlines()
    os.remove(f"./{Path(filepath).with_suffix('').name}.csv")

    attribute_list = ["Version", "Signature", "ExecutableName", "PrefetchHash", "SectionAEntriesCount", "SectionBEntriesCount", "SectionCLength", "SectionDEntriesCount", "LastExecutionTime", "ExecutionCount", "VolumeDevicePath", "VolumeCreateTime", "VolumeSerialNumber", "FileMetricsArrayCount", "TraceChainArrayCount", "FileReferenceCount", "DirectoryStringsCount", "FileNameStrings"]

    result = []
    for line in csv_lines:
        temp = {}
        for i, attr in enumerate(line.split(',')[1:]):
            if '|' in attr:
                temp[attribute_list[i]] = attr.split('|')
            else:
                temp[attribute_list[i]] = attr
        else:
            result.append(temp)

    es = ElasticsearchUtils(hostname=host, port=port)

    try:
        es.bulk_indice(result, index, type)
    except Exception:
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('prefetchfile', help='Windows Prefetch')
    parser.add_argument('--host', default='localhost', help='ElasticSearch host address')
    parser.add_argument('--port', default=9200, help='ElasticSearch port number')
    parser.add_argument('--index', default='prefetch2es', help='Index name')
    parser.add_argument('--type', default='prefetch2es', help='Document type name')
    parser.add_argument('--size', default=500, help='Bulk insert buffer size')
    args = parser.parse_args()

    prefetch2es(
        filepath=args.prefetchfile,
        host=args.host,
        port=int(args.port),
        index=args.index,
        type=args.type,
        size=int(args.size)
    )


if __name__ == '__main__':
    main()
