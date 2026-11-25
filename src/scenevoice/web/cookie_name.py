def cookie_name(port: int) -> str:
    """Port-named so two instances do not overwrite each other (a mitigation, not isolation)."""
    return f"scenevoice_{port}"
