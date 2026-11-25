import argparse
from typing import NoReturn

from scenevoice.cli.keys_usage_error import keys_usage_error


class KeysParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        keys_usage_error()
