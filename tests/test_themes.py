"""Tests for Spook's own themes, delivered to the frontend without YAML."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.components.frontend import (
    DATA_DEFAULT_DARK_THEME,
    DATA_DEFAULT_THEME,
    DATA_THEMES,
    validate_themes,
)
from homeassistant.const import EVENT_THEMES_UPDATED
from homeassistant.core import callback
from homeassistant.setup import async_setup_component

from custom_components.spook.themes import THEMES_PATH, async_setup_themes, load_themes

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from pytest_homeassistant.typing import WebSocketGenerator

    from homeassistant.core import Event, HomeAssistant

# A theme of somebody's own, in their `configuration.yaml`.
_CONFIGURATION = """\
frontend:
  themes:
    Midnight:
      primary-color: "#000033"
"""


@pytest.fixture(name="configuration_yaml")
def fixture_configuration_yaml(
    hass: HomeAssistant,
) -> Iterator[Callable[[str], None]]:
    """Write the `configuration.yaml` a theme reload reads its themes from."""
    path = Path(hass.config.config_dir) / "configuration.yaml"

    def _write(content: str) -> None:
        path.write_text(content, encoding="utf-8")

    _write(_CONFIGURATION)
    yield _write
    path.unlink(missing_ok=True)


async def _async_setup_frontend(
    hass: HomeAssistant, tmp_path: Path, themes: dict[str, Any] | None = None
) -> None:
    """Set up the frontend, the way Home Assistant does before Spook.

    The frontend's files are not installed for the tests, so it is pointed at
    an empty development checkout instead. Themes do not care either way.
    """
    (tmp_path / "hass_frontend").mkdir(exist_ok=True)
    themes = (
        themes if themes is not None else {"Midnight": {"primary-color": "#000033"}}
    )
    assert await async_setup_component(
        hass,
        "frontend",
        {"frontend": {"development_repo": str(tmp_path), "themes": themes}},
    )


async def _async_set_theme(hass: HomeAssistant, **data: str) -> None:
    """Pick the default theme, the way the profile page and automations do."""
    await hass.services.async_call("frontend", "set_theme", data, blocking=True)


async def _async_reload_themes(hass: HomeAssistant) -> None:
    """Reload the themes from YAML, the way the Marketplace does after an install."""
    await hass.services.async_call("frontend", "reload_themes", blocking=True)
    await hass.async_block_till_done()


def _count_themes_updated(hass: HomeAssistant) -> list[Event]:
    """Return the list every `themes_updated` event lands in."""
    fired: list[Event] = []

    @callback
    def _async_note(event: Event) -> None:
        fired.append(event)

    hass.bus.async_listen(EVENT_THEMES_UPDATED, _async_note)
    return fired


def _defaults(hass: HomeAssistant) -> tuple[str, str | None]:
    """Return the default light and dark theme the frontend holds."""
    return hass.data[DATA_DEFAULT_THEME], hass.data.get(DATA_DEFAULT_DARK_THEME)


def test_theme_files_are_themes() -> None:
    """Every file is a theme core's own schema takes, with both modes.

    Core skips a theme it does not like and only logs it. Spook does not run
    them through the schema, so a broken one would just be missing.
    """
    assert sorted(path.name for path in THEMES_PATH.glob("*.yaml")) == ["spook.yaml"]

    themes = load_themes()
    assert list(themes) == ["Spook"]
    assert validate_themes(themes) == themes
    assert set(themes["Spook"]["modes"]) == {"light", "dark"}


async def test_themes_reach_browsers(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, tmp_path: Path
) -> None:
    """Set up, the theme is in the list browsers get, and can be picked."""
    await _async_setup_frontend(hass, tmp_path)
    fired = _count_themes_updated(hass)

    await async_setup_themes(hass)
    assert len(fired) == 1

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "frontend/get_themes"})
    response = await client.receive_json()
    assert response["success"]
    assert set(response["result"]["themes"]) == {"Midnight", "Spook"}

    await _async_set_theme(hass, name="Spook", name_dark="Spook")
    assert _defaults(hass) == ("Spook", "Spook")


async def test_themes_back_after_a_reload(
    hass: HomeAssistant,
    tmp_path: Path,
    configuration_yaml: Callable[[str], None],
) -> None:
    """A theme reload drops the theme, and it is back without going in circles.

    One event from the reload, one from putting the theme back. A third would
    mean Spook answers its own event.
    """
    await _async_setup_frontend(hass, tmp_path)
    await async_setup_themes(hass)

    # A theme installed in the meantime, and found by the reload.
    configuration_yaml(_CONFIGURATION + '    Forest:\n      primary-color: "#004400"\n')
    fired = _count_themes_updated(hass)
    await _async_reload_themes(hass)

    assert set(hass.data[DATA_THEMES]) == {"Midnight", "Forest", "Spook"}
    assert [event.event_type for event in fired] == [EVENT_THEMES_UPDATED] * 2


@pytest.mark.usefixtures("configuration_yaml")
async def test_default_back_after_a_reload(hass: HomeAssistant, tmp_path: Path) -> None:
    """A reload resets a default that is Spook's theme, and it is put back."""
    await _async_setup_frontend(hass, tmp_path)
    await async_setup_themes(hass)
    await _async_set_theme(hass, name="Spook", name_dark="Spook")

    await _async_reload_themes(hass)

    assert _defaults(hass) == ("Spook", "Spook")


@pytest.mark.usefixtures("configuration_yaml")
async def test_default_picked_since_stays(hass: HomeAssistant, tmp_path: Path) -> None:
    """A default somebody moved away from Spook's theme is not taken back."""
    await _async_setup_frontend(hass, tmp_path)
    await async_setup_themes(hass)
    await _async_set_theme(hass, name="Spook", name_dark="Spook")
    await _async_set_theme(hass, name="Midnight", name_dark="none")

    await _async_reload_themes(hass)

    assert _defaults(hass) == ("Midnight", None)


async def test_default_back_after_a_restart(
    hass: HomeAssistant, hass_storage: dict[str, Any], tmp_path: Path
) -> None:
    """The frontend drops a stored default it does not know yet, Spook puts it back."""
    hass_storage["frontend_theme"] = {
        "version": 1,
        "key": "frontend_theme",
        "data": {
            DATA_DEFAULT_THEME: "Spook",
            DATA_DEFAULT_DARK_THEME: "Spook",
        },
    }
    await _async_setup_frontend(hass, tmp_path)
    assert _defaults(hass) == ("default", None)

    await async_setup_themes(hass)

    assert _defaults(hass) == ("Spook", "Spook")


async def test_stored_default_of_another_theme_stays(
    hass: HomeAssistant, hass_storage: dict[str, Any], tmp_path: Path
) -> None:
    """A stored default that is not Spook's theme is left alone."""
    hass_storage["frontend_theme"] = {
        "version": 1,
        "key": "frontend_theme",
        "data": {DATA_DEFAULT_THEME: "Midnight", DATA_DEFAULT_DARK_THEME: None},
    }
    await _async_setup_frontend(hass, tmp_path)

    await async_setup_themes(hass)

    assert _defaults(hass) == ("Midnight", None)


async def test_own_theme_by_that_name_wins(hass: HomeAssistant, tmp_path: Path) -> None:
    """Somebody's own theme named Spook stays theirs, and stays on unload."""
    theirs = {"primary-color": "#ff00ff"}
    await _async_setup_frontend(hass, tmp_path, {"Spook": theirs})

    stop = await async_setup_themes(hass)
    assert hass.data[DATA_THEMES]["Spook"] == theirs

    stop()
    assert hass.data[DATA_THEMES]["Spook"] == theirs


@pytest.mark.usefixtures("configuration_yaml")
async def test_unload(hass: HomeAssistant, tmp_path: Path) -> None:
    """Spook going takes the theme out, and a default on it with it.

    Left pointing at a theme that is gone, the frontend fails on the next
    default somebody picks. After the unload a reload no longer brings the
    theme back either.
    """
    await _async_setup_frontend(hass, tmp_path)
    stop = await async_setup_themes(hass)
    await _async_set_theme(hass, name="Spook", name_dark="Spook")

    fired = _count_themes_updated(hass)
    stop()

    assert "Spook" not in hass.data[DATA_THEMES]
    assert _defaults(hass) == ("default", None)
    assert len(fired) == 1

    await _async_set_theme(hass, name_dark="Midnight")
    assert _defaults(hass) == ("default", "Midnight")

    await _async_reload_themes(hass)
    assert "Spook" not in hass.data[DATA_THEMES]


async def test_loaded_again_brings_the_default_back(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Spook reloaded picks up the default it reset on its way out.

    The frontend stores a picked default after a minute. Past that, the
    stored one is still Spook's theme.
    """
    await _async_setup_frontend(hass, tmp_path)
    stop = await async_setup_themes(hass)
    await _async_set_theme(hass, name="Spook")
    await hass.data["frontend_themes_store"].async_save(
        {DATA_DEFAULT_THEME: "Spook", DATA_DEFAULT_DARK_THEME: None}
    )

    stop()
    assert _defaults(hass) == ("default", None)

    await async_setup_themes(hass)
    assert _defaults(hass) == ("Spook", None)


async def test_without_a_frontend(hass: HomeAssistant) -> None:
    """No frontend, no list of themes, nothing to do and nothing to undo."""
    stop = await async_setup_themes(hass)
    stop()

    assert DATA_THEMES not in hass.data
