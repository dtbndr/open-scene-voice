from pathlib import Path

from scenevoice.synth.parse_record import parse_record
from scenevoice.synth.record_entry import RecordEntry
from scenevoice.synth.record_name import RECORD_NAME
from scenevoice.validation import Violation


def load_record(out_dir: Path) -> tuple[RecordEntry, ...] | Violation | None:
    """Read DIR/synth_record.json: None when absent, a Violation when unreadable or malformed."""
    path = Path(out_dir) / RECORD_NAME
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError:
        return parse_record(b"")  # unreadable: the one malformed Violation
    return parse_record(data)
