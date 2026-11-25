"""AST import-direction guard: pack and synth never reach align; synth never reaches pack."""

import ast
from pathlib import Path

import pytest
from paths_helper import REPO_ROOT

SRC = REPO_ROOT / "src"


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


def test_scanner_sees_the_real_tree():
    files = list((SRC / "scenevoice" / "pack").rglob("*.py"))
    assert len(files) > 5
    assert any("scenevoice.synth" in imported_modules(p.read_text(encoding="utf-8"), "scenevoice.pack") for p in files)


@pytest.mark.parametrize("subpackage", ["pack", "synth"])
def test_pack_and_synth_never_import_align(subpackage):
    assert violations(SRC, subpackage, ["scenevoice.align"]) == []


def test_synth_never_imports_pack():
    assert violations(SRC, "synth", ["scenevoice.pack"]) == []


ALIGN_ALLOWED = {"scenevoice.align.split_sentences", "scenevoice.align.split_sentences.split_sentences"}


def package_imports(source_root: Path, subpackage: str) -> dict[str, set[str]]:
    result = {}
    for path in sorted((source_root / "scenevoice" / subpackage).rglob("*.py")):
        package = ".".join(path.relative_to(source_root).with_suffix("").parts[:-1])
        result[path.name] = imported_modules(path.read_text(encoding="utf-8"), package)
    return result


def align_leaks(imports: dict[str, set[str]]) -> list[str]:
    return sorted(
        f"{name} imports {m}"
        for name, modules in imports.items()
        for m in modules
        if reaches({m}, "scenevoice.align") and m not in ALIGN_ALLOWED
    )


def test_scanner_sees_the_real_beats_tree():
    imports = package_imports(SRC, "beats")
    assert len(imports) > 10
    assert any("scenevoice.align.split_sentences" in modules for modules in imports.values())


def test_beats_never_imports_pack():
    assert violations(SRC, "beats", ["scenevoice.pack"]) == []


def test_beats_imports_align_only_as_split_sentences():
    assert align_leaks(package_imports(SRC, "beats")) == []


@pytest.mark.parametrize("subpackage", ["align", "pack", "beats"])
def test_openrouter_imports_no_feature_package(subpackage):
    assert len(package_imports(SRC, "openrouter")) > 5
    assert violations(SRC, "openrouter", [f"scenevoice.{subpackage}"]) == []


def test_beats_rule_checkers_can_fail():
    bad = {
        "a.py": imported_modules("from scenevoice.align import run_align\n", "scenevoice.beats"),
        "b.py": imported_modules("import scenevoice.align\n", "scenevoice.beats"),
    }
    assert align_leaks(bad) != []
    assert align_leaks({"b.py": bad["b.py"]}) != []
    ok = {"c.py": imported_modules("from scenevoice.align.split_sentences import split_sentences\n", "scenevoice.beats")}
    assert align_leaks(ok) == []
    assert reaches(imported_modules("from scenevoice import pack\n", "scenevoice.beats"), "scenevoice.pack")


def test_keys_never_imports_synth():
    assert violations(SRC, "keys", ["scenevoice.synth"]) == []


WEB_FORBIDDEN = [
    *(
        f"scenevoice.{name}"
        for name in ("openrouter", "align", "pack", "beats", "cli", "plan", "progress", "validation")
    ),
    *(
        f"scenevoice.keys.{path.stem}"
        for path in sorted((SRC / "scenevoice" / "keys").glob("*.py"))
        if path.stem not in ("__init__", "key_names")
    ),
]


def test_web_imports_only_key_names_from_keys():
    imports = package_imports(SRC, "web")
    assert len(imports) > 5
    assert any("scenevoice.keys.key_names" in modules for modules in imports.values())
    assert len(WEB_FORBIDDEN) > 15
    assert violations(SRC, "web", WEB_FORBIDDEN) == []
    # WS47 slice A: the read-only catalog route is the one web module that reads the synth registry (no calls, no files).
    assert [name for name, modules in imports.items() if any(m.startswith("scenevoice.synth") for m in modules)] == ["get_catalog.py"]
    assert [name for name, modules in imports.items() if "scenevoice.keys" in modules] == []
