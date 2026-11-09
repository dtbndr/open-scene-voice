from difflib import SequenceMatcher


def matched_indexes(script: list[str], heard: list[str]) -> dict[int, int]:
    """Map each script token position inside a matching block to its heard position.

    Uses difflib with autojunk off; its get_matching_blocks() is the reference.
    """
    blocks = SequenceMatcher(None, script, heard, autojunk=False).get_matching_blocks()
    return {
        block.a + offset: block.b + offset
        for block in blocks
        for offset in range(block.size)
    }
