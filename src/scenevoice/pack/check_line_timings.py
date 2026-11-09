from pathlib import Path

from scenevoice.pack.fresh_timings import fresh_timings
from scenevoice.pack.parse_line_timings import parse_line_timings
from scenevoice.pack.read_line_timings_file import read_line_timings_file
from scenevoice.pack.timings_freshness import TimingsFreshness
from scenevoice.synth import PlanScene, SceneWav


def check_line_timings(
    directory: str | Path, scenes: list[PlanScene], wavs: list[SceneWav]
) -> tuple[TimingsFreshness, bool] | str:
    """Check 4a (editor runs only): the freshness per scene from the held WAV bytes, plus whether the file was absent.

    Returns a one-line failure message for a present but unusable file. An absent file gives (empty freshness, True).
    """
    content = read_line_timings_file(directory)
    if isinstance(content, str):
        return content
    if content is None:
        return TimingsFreshness(), True
    table = parse_line_timings(content)
    if isinstance(table, str):
        return table
    freshness = fresh_timings(table, [(s.ordinal, w.data) for s, w in zip(scenes, wavs, strict=True)])
    return freshness, False
