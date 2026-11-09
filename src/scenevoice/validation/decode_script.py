from scenevoice.validation.violation import Violation

_BOM = b"\xef\xbb\xbf"


def decode_script(data: bytes) -> str | Violation:
    if data.startswith(_BOM):
        return Violation("bom", "file starts with a UTF-8 byte order mark (BOM); save it without one", 1)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        line = 1 + data[: error.start].count(b"\n")
        byte = data[error.start]
        return Violation("invalid-utf8", f"invalid UTF-8 byte 0x{byte:02x}", line)
