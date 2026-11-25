"""Constants for the beats sidecar (WS35 decision 7)."""

SIDECAR_VERSION = 1
MAX_NOTE_CHARS = 200
MAX_SCRIPT_CHARS = 20000
BEATS_MAX_TOKENS = 8000
SCRIPT_TOO_LONG_MESSAGE = (
    f"the script is too long (the limit is {MAX_SCRIPT_CHARS} characters)"
)
