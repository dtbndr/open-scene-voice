from scenevoice.validation.load_scenes import load_scenes
from scenevoice.validation.violation import Violation


# Returns only the violation; the parsed scenes are discarded.
def validate_script(data: bytes) -> Violation | None:
    loaded = load_scenes(data)
    return loaded if isinstance(loaded, Violation) else None
