"""AST import-direction guard: pack and synth never reach align; synth never reaches pack."""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"


def imported_modules(source: str, package: str) -> set[str]:
    """Absolute dotted names a module imports; `from a import b` also yields `a.b`."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")
                parts = parts[: len(parts) - (node.level - 1)]
                base = ".".join(parts + ([node.module] if node.module else []))
            found.add(base)
            found.update(f"{base}.{alias.name}" for alias in node.names)
    return found


def reaches(modules: set[str], target: str) -> bool:
    return any(m == target or m.startswith(target + ".") for m in modules)


def violations(source_root: Path, subpackage: str, forbidden: list[str]) -> list[str]:
    bad = []
    for path in sorted((source_root / "scenevoice" / subpackage).rglob("*.py")):
        relative = path.relative_to(source_root).with_suffix("")
        package = ".".join(relative.parts[:-1])
        modules = imported_modules(path.read_text(encoding="utf-8"), package)
        bad.extend(f"{path.name} imports {t}" for t in forbidden if reaches(modules, t))
    return bad


def test_scanner_flags_every_offending_form():
    for source in (
        "from scenevoice import align\n",
        "import scenevoice.align.run_align\n",
        "from scenevoice.align import x\n",
        "from scenevoice.align.run_align import run_align\n",
        "def f():\n    from scenevoice import align\n",
    ):
        assert reaches(imported_modules(source, "scenevoice.pack"), "scenevoice.align"), source


def test_scanner_flags_relative_forms():
    assert reaches(imported_modules("from ..align import x\n", "scenevoice.pack"), "scenevoice.align")
    assert reaches(imported_modules("from .. import align\n", "scenevoice.pack"), "scenevoice.align")
    assert reaches(imported_modules("from .. import pack\n", "scenevoice.synth"), "scenevoice.pack")


def test_scanner_passes_innocent_imports():
    modules = imported_modules("import os\nfrom scenevoice.synth import x\nfrom . import y\n", "scenevoice.pack")
    assert not reaches(modules, "scenevoice.align")


def test_scanner_sees_the_real_tree():
    files = list((SRC / "scenevoice" / "pack").rglob("*.py"))
    assert len(files) > 5
    assert any("scenevoice.synth" in imported_modules(p.read_text(encoding="utf-8"), "scenevoice.pack") for p in files)


@pytest.mark.parametrize("subpackage", ["pack", "synth"])
def test_pack_and_synth_never_import_align(subpackage):
    assert violations(SRC, subpackage, ["scenevoice.align"]) == []


def test_synth_never_imports_pack():
    assert violations(SRC, "synth", ["scenevoice.pack"]) == []
