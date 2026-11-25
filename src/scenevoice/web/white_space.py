import re

# Unicode White_Space exactly, a copy of `scenevoice.align.white_space` (`web` must not import align); a drift test
# pins the two together. Not \s and not str.split(): both also accept U+001C-001F.
WHITE_SPACE_CHARS = "\t-\r \x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000"
WHITE_SPACE_RUN = re.compile(f"[{WHITE_SPACE_CHARS}]+")
