def format_duration(frames: int) -> str:
    """Seconds at 24000 Hz, exact integer maths, 3 decimals, ties round up."""
    millis = (frames * 1000 + 12000) // 24000
    return f"{millis // 1000}.{millis % 1000:03d}"
