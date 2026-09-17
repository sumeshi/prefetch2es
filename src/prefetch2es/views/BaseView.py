# coding: utf-8
import argparse
from abc import ABCMeta, abstractmethod

from prefetch2es.models.MetaData import get_version


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


class BaseView(metaclass=ABCMeta):

    def __init__(self):
        self.parser = argparse.ArgumentParser(allow_abbrev=False)
        self.__define_common_options()

    def __define_common_options(self):
        self.parser.add_argument(
            "--version", "-v", action="version", version=get_version("prefetch2es")
        )
        self.parser.add_argument(
            "--quiet",
            "-q",
            action="store_true",
            help="Suppress standard output.",
        )
        self.parser.add_argument(
            "--multiprocess",
            "-m",
            action="store_true",
            help="Enable multiprocessing.",
        )
        self.parser.add_argument(
            "--size",
            "-s",
            type=positive_int,
            default=500,
            help="Number of files to process in each chunk.",
        )

    @abstractmethod
    def define_options(self):
        pass

    def log(self, message: str, is_quiet: bool):
        if not is_quiet:
            print(message)
