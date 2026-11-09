def missing_record_note(ordinal: int) -> str:
    """NOTE text (no prefix) for a --scene run with no synth_record.json."""
    return (
        f"no settings recorded for scene {ordinal} "
        "(synth_record.json is missing); settings not checked"
    )


def missing_entry_note(ordinal: int) -> str:
    """NOTE text (no prefix) for a record that has no entry for the scene."""
    return (
        f"no settings recorded for scene {ordinal} in synth_record.json; "
        "settings not checked"
    )
