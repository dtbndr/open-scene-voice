from scenevoice.validation.check_controls import check_controls
from scenevoice.validation.check_cr import check_cr
from scenevoice.validation.decode_script import decode_script
from scenevoice.validation.parse_scenes import parse_scenes
from scenevoice.validation.scene import Scene
from scenevoice.validation.violation import Violation


# Lexical checks run first, in order; scene parsing runs last, only on text that passed them.
def load_scenes(data: bytes) -> list[Scene] | Violation:
    decoded = decode_script(data)
    if isinstance(decoded, Violation):
        return decoded
    lexical = check_cr(decoded) or check_controls(decoded)
    if lexical is not None:
        return lexical
    return parse_scenes(decoded)
