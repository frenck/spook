"""Tests for names a package's own modules take over."""

from __future__ import annotations

import ast
from pathlib import Path
import symtable

import pytest

SPOOK_ROOT = Path(__file__).parents[1] / "custom_components" / "spook"


def _submodule_names(package: Path) -> set[str]:
    """Return the names of the modules and packages directly in a package."""
    return {
        path.stem
        for path in package.iterdir()
        if (path.suffix == ".py" and path.name != "__init__.py")
        or (path / "__init__.py").is_file()
    }


def _globals_read(table: symtable.SymbolTable) -> set[str]:
    """Return every name the code reads from the module namespace.

    A function's own local of the same name never reaches the namespace, so
    only names that resolve to it count.
    """
    names = {
        symbol.get_name()
        for symbol in table.get_symbols()
        if symbol.is_referenced()
        and (table.get_type() == "module" or symbol.is_global())
    }
    for child in table.get_children():
        names |= _globals_read(child)

    return names


def _submodules_imported_on_purpose(tree: ast.Module) -> set[str]:
    """Return the submodules the package imports itself, under their own name."""
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level == 1 and not node.module
        for alias in node.names
        if alias.asname is None
    }


@pytest.mark.parametrize(
    "init_file",
    sorted(SPOOK_ROOT.rglob("__init__.py")),
    ids=lambda path: str(path.parent.relative_to(SPOOK_ROOT)) or ".",
)
def test_no_package_reads_a_name_its_submodules_take_over(init_file: Path) -> None:
    """Test no package's own code reads a name one of its modules also has.

    A package's `__init__.py` runs in the package namespace, and importing a
    submodule binds it there under its own name. Spook imports every action
    module when it sets up, so `number.max` and `number.min` turned `max` and
    `min` in `number/services/__init__.py` into modules, and every step failed
    with "'module' object is not callable". Tests that only imported some of
    the modules never saw it. #1944
    """
    source = init_file.read_text(encoding="utf-8")
    table = symtable.symtable(source, str(init_file), "exec")

    taken_over = (
        _globals_read(table) & _submodule_names(init_file.parent)
    ) - _submodules_imported_on_purpose(ast.parse(source))

    assert not taken_over, (
        f"{init_file.relative_to(SPOOK_ROOT)} reads {sorted(taken_over)}, "
        "which a submodule replaces once it is imported. Move the code into "
        "a sibling module, like stepping.py"
    )
