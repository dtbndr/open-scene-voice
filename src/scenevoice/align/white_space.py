import re

# Unicode White_Space exactly. Not \s and not str.split(): both also accept
# U+001C-001F, which are not White_Space.
WHITE_SPACE_CHARS = (
    "\u0009-\u000d \u0085   - "
    "    　"
)
WHITE_SPACE_RUN = re.compile(f"[{WHITE_SPACE_CHARS}]+")
