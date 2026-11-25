class SlotRefused(Exception):
    """`start` was given a handle that was released, cancelled, closed by shutdown or already started."""
