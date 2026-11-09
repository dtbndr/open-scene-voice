from scenevoice.pack.line_timing import LineTiming
from scenevoice.pack.timeline_constants import FRAME_RATE

Clip = tuple[int, int, int, list[LineTiming]]
Placed = tuple[int, int, int]


def place_markers(clips: list[Clip]) -> tuple[list[Placed], list[tuple[int, int]]]:
    """Place scene and line markers; clips are (ordinal, start frame, frames, lines).

    Returns (frame, ordinal, number) for each placed marker in ascending frame order (number 0 is the
    scene marker) and the skipped (ordinal, number) pairs in plan then line order.
    """
    placed: list[Placed] = []
    skipped: list[tuple[int, int]] = []
    for ordinal, start, frames, lines in clips:
        last = start + frames - 1
        wanted: list[tuple[int, int, int]] = [(start, 0, 0)]
        for number, line in enumerate(lines, 1):
            if line.start_ms is not None:
                frame = start + (line.start_ms * FRAME_RATE + 500) // 1000
                wanted.append((min(frame, last), 1, number))
        taken: set[int] = set()
        missed: list[int] = []
        for frame, _, number in sorted(wanted):
            while frame in taken and frame <= last:
                frame += 1
            if frame > last:
                missed.append(number)
                continue
            taken.add(frame)
            placed.append((frame, ordinal, number))
        skipped.extend((ordinal, number) for number in sorted(missed))
    placed.sort()
    return placed, skipped
