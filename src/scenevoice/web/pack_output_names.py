from collections.abc import Iterable

from .build_pack_zip import PACK_OUTPUTS


def pack_output_names(project_names: Iterable[str]) -> list[str]:
    """The pack outputs (the manifest and the timeline, exact names) found in a project folder listing, in the pack's order."""
    present = set(project_names)
    return [name for name in PACK_OUTPUTS if name in present]
