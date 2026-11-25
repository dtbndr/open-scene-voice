import argparse

from scenevoice.web import DEFAULT_PORT


def _port_number(value: str) -> int:
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a whole number from 1024 to 65535") from None
    if not 1024 <= port <= 65535:
        raise argparse.ArgumentTypeError("must be a whole number from 1024 to 65535")
    return port


def add_web_parser(subparsers) -> None:
    web = subparsers.add_parser(
        "web",
        allow_abbrev=False,
        help="open SceneVoice in your browser (this computer only)",
        description="Starts SceneVoice's local web page on this computer and opens it in your browser. "
        "Keep the window open while you work; press Control-C to stop. Only this computer can reach it.",
    )
    web.add_argument(
        "--port", type=_port_number, default=DEFAULT_PORT, metavar="N",
        help=f"port to listen on, 1024 to 65535 (default {DEFAULT_PORT}); the same port keeps old browser tabs useful",
    )
    web.add_argument("--no-open", action="store_true", help="print the link but do not open the browser")
