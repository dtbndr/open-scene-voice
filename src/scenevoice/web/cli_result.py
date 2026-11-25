from dataclasses import dataclass


@dataclass(frozen=True)
class CliResult:
    """Outcome of one child run; returncode -1 with empty output marks a timeout or undecodable output."""

    returncode: int
    stdout: str
    stderr: str
    timed_out: bool
