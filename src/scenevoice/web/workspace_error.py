class WorkspaceError(Exception):
    """A workspace problem with a plain-words message."""


class WorkspaceKeyFileError(WorkspaceError):
    """The workspace folder holds the key file."""


class FileTooLargeError(Exception):
    """A project file holds more bytes than the caller's cap."""


KEY_FILE_MESSAGE = "The workspace folder holds your key file. Choose another folder."


class NothingPackedError(Exception):
    """The project has no usable `scene_manifest.csv`, so nothing has been packed."""


class PackTooLargeError(Exception):
    """The files to zip add up to more than the cap."""
