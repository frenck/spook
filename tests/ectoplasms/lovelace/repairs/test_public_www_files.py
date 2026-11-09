"""Tests for the Lovelace public www files repair."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.components.frontend import DATA_THEMES

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.lovelace.repairs.public_www_files import (
    SpookRepair,
)

if TYPE_CHECKING:
    from pathlib import Path

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

_ISSUE = "lovelace_public_www_files_{}"


@pytest.fixture(name="www")
def www_fixture(hass: HomeAssistant, tmp_path: Path) -> Path:
    """Return a `www` folder of this test's own.

    The configuration directory is shared by the whole session, and files
    another test left in its `www` would end up in these findings.
    """
    hass.config.config_dir = str(tmp_path)
    return tmp_path / "www"


def _write(www: Path, *names: str) -> None:
    """Create these files under `www`."""
    for name in names:
        path = www / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("here", encoding="utf-8")


def _set_dashboards(hass: HomeAssistant, *configs: dict[str, Any]) -> None:
    """Install dashboards with these configs."""

    def dashboard(url_path: str, config: dict[str, Any]) -> SimpleNamespace:
        async def async_load(*, force: bool) -> dict[str, Any]:
            del force
            return config

        return SimpleNamespace(url_path=url_path, config={}, async_load=async_load)

    hass.data["lovelace"] = SimpleNamespace(
        dashboards={
            f"dashboard-{index}": dashboard(f"dashboard-{index}", config)
            for index, config in enumerate(configs)
        }
    )


async def _async_inspect(hass: HomeAssistant) -> SpookRepair:
    """Run one inspection, cleanup included, and return the repair."""
    repair = SpookRepair(hass)
    repair._dashboards = hass.data["lovelace"].dashboards  # noqa: SLF001
    await repair._async_inspect_with_cleanup()  # noqa: SLF001
    return repair


def _issue(issue_registry: ir.IssueRegistry, folder: str) -> ir.IssueEntry | None:
    """Return the issue about this folder, if there is one."""
    return issue_registry.async_get_issue(DOMAIN, _ISSUE.format(folder))


async def test_files_an_integration_left_are_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test a folder of files nobody put up on purpose is reported."""
    await hass.async_add_executor_job(
        _write,
        www,
        *(f"printer/cover_{index:02}.png" for index in range(12)),
        "printer/jobs/latest.3mf",
    )
    _set_dashboards(hass)

    await _async_inspect(hass)

    issue = _issue(issue_registry, "printer")
    assert issue
    assert issue.translation_key == "lovelace_public_www_files"
    assert issue.translation_placeholders
    assert issue.translation_placeholders["folder"] == "/local/printer/"
    assert issue.translation_placeholders["count"] == "13"
    # Only the first few are listed, in a stable order.
    assert issue.translation_placeholders["files"] == "\n".join(
        f"- `/local/printer/cover_{index:02}.png`" for index in range(10)
    )


async def test_files_straight_in_www_are_reported_together(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test loose files share one issue, and loose code is left alone.

    A folder that happens to be called `www` gets an issue of its own.
    """
    await hass.async_add_executor_job(
        _write, www, "snapshot.jpg", "notes.txt", "my-card.js", "www/cover.png"
    )
    _set_dashboards(hass)

    await _async_inspect(hass)

    issue = _issue(issue_registry, ".")
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["folder"] == "/local/"
    assert issue.translation_placeholders["files"] == (
        "- `/local/notes.txt`\n- `/local/snapshot.jpg`"
    )
    issue = _issue(issue_registry, "www")
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["folder"] == "/local/www/"


async def test_what_is_put_up_on_purpose_is_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test the Marketplace, cards, hidden files and linked files are left alone."""
    await hass.async_add_executor_job(
        _write,
        www,
        "community/some-card/some-card.js",
        "community/some-card/preview.png",
        "manual-card/manual-card.js",
        "manual-card/icons/logo.svg",
        ".DS_Store",
        "floorplan/.hidden/backup.png",
        "floorplan/ground floor.png",
        "floorplan/first.png",
        "floorplan/legend.png",
        "floorplan/notes.png",
        "backgrounds/night.jpg",
    )
    hass.data[DATA_THEMES] = {
        "dark": {
            "lovelace-background": 'center / cover url("/local/backgrounds/night.jpg")'
        }
    }
    _set_dashboards(
        hass,
        {
            "views": [
                {
                    "cards": [
                        {
                            "type": "picture-elements",
                            "image": "/local/floorplan/ground%20floor.png?v=2",
                        },
                        {
                            "type": "custom:fancy-card",
                            "layers": [
                                {
                                    "src": "https://ha.example.com/local/floorplan/first.png"
                                }
                            ],
                        },
                        {
                            "type": "markdown",
                            "content": (
                                "![Legend](/local/floorplan/legend.png) "
                                '<img src="/local/floorplan/notes.png">'
                            ),
                        },
                    ]
                }
            ]
        },
    )

    await _async_inspect(hass)

    assert not [
        issue_id
        for domain, issue_id in issue_registry.issues
        if domain == DOMAIN and issue_id.startswith("lovelace_public_www_files")
    ]


@pytest.mark.usefixtures("www")
async def test_no_www_folder_is_a_no_op(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a configuration without a `www` folder raises nothing."""
    _set_dashboards(hass)

    await _async_inspect(hass)

    assert _issue(issue_registry, ".") is None


async def test_issue_goes_once_the_files_do(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test the issue is cleaned up when the folder is emptied."""
    await hass.async_add_executor_job(_write, www, "printer/cover.png")
    _set_dashboards(hass)

    repair = await _async_inspect(hass)
    assert _issue(issue_registry, "printer")

    await hass.async_add_executor_job((www / "printer" / "cover.png").unlink)
    await repair._async_inspect_with_cleanup()  # noqa: SLF001

    assert _issue(issue_registry, "printer") is None


async def test_ignoring_a_folder_outlasts_new_files(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    www: Path,
) -> None:
    """Test an ignored folder stays ignored when files are added to it.

    An integration writing here keeps adding files, and ignoring it is a
    decision about the folder, not about the files that were there then.
    """
    await hass.async_add_executor_job(_write, www, "printer/cover_1.png")
    _set_dashboards(hass)

    repair = await _async_inspect(hass)
    issue_registry.async_ignore(DOMAIN, _ISSUE.format("printer"), ignore=True)

    await hass.async_add_executor_job(_write, www, "printer/cover_2.png")
    await repair._async_inspect_with_cleanup()  # noqa: SLF001

    issue = _issue(issue_registry, "printer")
    assert issue
    assert issue.dismissed_version is not None
    assert issue.translation_placeholders
    assert issue.translation_placeholders["count"] == "2"
