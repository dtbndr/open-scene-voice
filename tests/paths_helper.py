"""Repo-relative path constants, so moved tests never count parent levels."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures"
