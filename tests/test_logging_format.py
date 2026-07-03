"""Tests for logger call formatting across the Spook codebase."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SPOOK_DIR = Path(__file__).parent.parent / "custom_components" / "spook"
LOGGER_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}

MODULES = sorted(
    path
    for path in SPOOK_DIR.rglob("*.py")
    if "__pycache__" not in path.parts and ".venv" not in path.parts
)


@pytest.mark.parametrize(
    "module", MODULES, ids=[str(path.relative_to(SPOOK_DIR)) for path in MODULES]
)
def test_logger_calls_use_string_format(module: Path) -> None:
    """Test logger calls pass a string, not a tuple, as the format message.

    A stray trailing comma turns implicitly concatenated string literals into
    a single-element tuple, making the log record render as the tuple's repr
    instead of the intended message.
    """
    tree = ast.parse(module.read_text(encoding="utf-8"))

    offenders = [
        call.lineno
        for call in ast.walk(tree)
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr in LOGGER_METHODS
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "LOGGER"
        and call.args
        and isinstance(call.args[0], ast.Tuple)
    ]

    assert not offenders, (
        f"LOGGER call with a tuple as format message at "
        f"{module.relative_to(SPOOK_DIR)} line(s) {offenders}"
    )
