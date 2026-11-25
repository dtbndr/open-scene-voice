from scenevoice.cli.keys_parser import KeysParser
from scenevoice.cli.keys_usage_error import keys_usage_error
from scenevoice.keys import KEY_NAMES


def add_keys_parser(subparsers) -> None:
    keys = subparsers.add_parser(
        "keys",
        allow_abbrev=False,
        help="manage the per-user key file: show, save or remove keys (values come from standard input)",
        description="Manages the per-user key file. Values are read from standard input, "
        "never from the command line.",
    )
    # The group parser is built by the top-level subparsers, so override its error here.
    keys.error = keys_usage_error  # type: ignore[method-assign]
    keys_subparsers = keys.add_subparsers(dest="keys_command", required=True, parser_class=KeysParser)
    keys_subparsers.add_parser(
        "status",
        allow_abbrev=False,
        help="print which keys are saved in the key file as one JSON line",
        description="Prints one JSON line saying which known keys the key file holds. "
        "Secret values are never printed. It reports the key file only, not the environment.",
    )
    set_parser = keys_subparsers.add_parser(
        "set",
        allow_abbrev=False,
        help="save one key, reading its value from standard input",
        description="Saves one key in the key file. The value is read from standard input, "
        "never from the command line, for example: printf %s VALUE | scenevoice keys set NAME. "
        "One trailing newline is dropped.",
    )
    set_parser.add_argument("name", metavar="NAME", choices=KEY_NAMES, help="one of: " + ", ".join(KEY_NAMES))
    remove_parser = keys_subparsers.add_parser(
        "remove",
        allow_abbrev=False,
        help="remove one key from the key file",
        description="Removes one key from the key file.",
    )
    remove_parser.add_argument("name", metavar="NAME", choices=KEY_NAMES, help="one of: " + ", ".join(KEY_NAMES))
