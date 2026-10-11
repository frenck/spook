"""A small installed frontend, for the repairs about unknown icons.

Spook reads the icon list from the `hass_frontend` package, which the test
environment does not have. This writes one shaped like the real thing: an
`iconMetadata.json` naming the chunks, and the chunks mapping each name to
its path. Two chunks, so a list read from only one of them is noticed.
"""

from __future__ import annotations

import json
import sys
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

ICON_VERSION = "7.4.47"

# Names a test can rely on being drawn. `lightbulb-outline` is one letter
# away from `lightbulb-outlin`, which no other name here is.
ICON_NAMES = (
    "account-group",
    "home",
    "lightbulb",
    "lightbulb-outline",
    "sofa",
    "thermometer",
)


def install_frontend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    names: tuple[str, ...] = ICON_NAMES,
) -> Path:
    """Install a frontend with these icons, and return its icon folder."""
    root = tmp_path / "hass_frontend"
    folder = root / "static" / "mdi"
    folder.mkdir(parents=True)

    half = len(names) // 2
    parts = []
    for index, chunk in enumerate((names[:half], names[half:])):
        file = f"chunk{index}"
        (folder / f"{file}.json").write_text(json.dumps(dict.fromkeys(chunk, "M0 0")))
        parts.append({"file": file} if index == 0 else {"start": "l", "file": file})

    (folder / "iconMetadata.json").write_text(
        json.dumps({"version": ICON_VERSION, "parts": parts})
    )
    (folder / "iconList.json").write_text(
        json.dumps([{"name": name, "keywords": []} for name in names])
    )

    module = ModuleType("hass_frontend")
    module.where = lambda: root  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "hass_frontend", module)

    return folder


def uninstall_frontend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make sure no frontend can be imported, whatever the environment has."""
    monkeypatch.setitem(sys.modules, "hass_frontend", None)
