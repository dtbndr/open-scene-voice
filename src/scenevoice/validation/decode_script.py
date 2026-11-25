from scenevoice.validation.violation import Violation

_BOM = b"\xef\xbb\xbf"


def decode_script(data: bytes) -> str | Violation:
    if data.startswith(_BOM):
        return Violation("bom", "The file starts with a hidden marker. Save it as plain UTF-8 text without a byte order mark.", 1)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        line = 1 + data[: error.start].count(b"\n")
        return Violation("invalid-utf8", "The file is not plain UTF-8 text. Re-save it as UTF-8.", line)
