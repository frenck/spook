"""A config directory with blueprints in it, and Spook's update platform."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.components.blueprint import BLUEPRINT_SCHEMA
from homeassistant.components.blueprint.importer import ImportedBlueprint
from homeassistant.components.blueprint.models import Blueprint
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import Platform
from homeassistant.setup import async_setup_component
from homeassistant.util import yaml as yaml_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

from custom_components.spook.ectoplasms.blueprint.update import (
    async_setup_entry as async_set_up_updates,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

SOURCE = "https://community.home-assistant.io/t/spooky-motion-light/1"

# Written the way blueprints out in the wild are: `trigger` and `action`
# rather than `triggers` and `actions`. The domain's own schema rewrites those
# on load, which is precisely what the fingerprint has to see past.
MOTION_LIGHT = """
blueprint:
  name: Spooky motion light
  domain: automation
  source_url: {source}
  input:
    motion_entity:
      name: Motion sensor
    light_target:
      name: Light
trigger:
  - platform: state
    entity_id: !input motion_entity
    to: "on"
action:
  - service: light.turn_on
    entity_id: !input light_target
mode: restart
"""

# The same blueprint, with something changed that matters.
MOTION_LIGHT_CHANGED = MOTION_LIGHT.replace('to: "on"', 'to: "off"')
MOTION_LIGHT_CHANGED_AGAIN = MOTION_LIGHT.replace("mode: restart", "mode: queued")

# And the same again, asking for something nobody has set yet.
MOTION_LIGHT_WITH_NEW_INPUT = MOTION_LIGHT.replace(
    "    light_target:\n      name: Light\n",
    "    light_target:\n      name: Light\n    wait_time:\n      name: Wait time\n",
)

# No inputs at all, and no `input:` key to say so. The schema puts an empty
# one in on the way through, which is why both sides have to go through it.
NO_INPUTS = """
blueprint:
  name: Spooky fixed automation
  domain: automation
  source_url: {source}
trigger:
  - platform: state
    entity_id: binary_sensor.landing
action:
  - service: light.turn_on
    entity_id: light.landing
"""

A_SCRIPT_BLUEPRINT = """
blueprint:
  name: Spooky confirmable notification
  domain: script
  source_url: {source}
  input:
    notify_target:
      name: Where to send it
sequence:
  - service: notify.notify
    data:
      message: Boo
      target: !input notify_target
"""

A_SCRIPT_BLUEPRINT_CHANGED = A_SCRIPT_BLUEPRINT.replace("Boo", "Boo!")

A_SCRIPT_BLUEPRINT_WITH_NEW_INPUT = A_SCRIPT_BLUEPRINT.replace(
    "    notify_target:\n      name: Where to send it\n",
    "    notify_target:\n      name: Where to send it\n    title:\n      name: Title\n",
)

# Says it needs a Home Assistant nobody is running yet.
MOTION_LIGHT_FROM_THE_FUTURE = MOTION_LIGHT.replace(
    "  source_url: {source}\n",
    "  source_url: {source}\n  homeassistant:\n    min_version: 9999.1.0\n",
)

# Same domain, different blueprint. What a forum topic holding two of them
# hands back, since both were imported carrying the address of the topic.
ANOTHER_AUTOMATION_BLUEPRINT = MOTION_LIGHT.replace(
    "Spooky motion light",
    "Spooky doorbell chime",
)


@pytest.fixture(autouse=True)
async def _a_config_dir_of_our_own(
    hass: HomeAssistant,
    tmp_path: Path,
) -> AsyncGenerator[None]:
    """Give every test its own blueprint folder, and clear up after it.

    The platform is unloaded on the way out so its check timer, which is set
    for somewhere between five and thirty minutes ahead, does not outlive the
    test that started it.
    """
    hass.config.config_dir = str(tmp_path)
    async_write_config(hass)

    yield

    for entry in hass.config_entries.async_entries("fake"):
        await hass.config_entries.async_unload(entry.entry_id)


def async_write_config(
    hass: HomeAssistant,
    automations: list[dict[str, Any]] | None = None,
) -> None:
    """Write the configuration.yaml a reload will read back."""
    Path(hass.config.path("configuration.yaml")).write_text(
        yaml_util.dump({"automation": automations or []}),
        encoding="utf-8",
    )


def async_write_blueprint(
    hass: HomeAssistant,
    domain: str,
    path: str,
    raw: str,
    *,
    source: str = SOURCE,
) -> Path:
    """Put a blueprint on disk the way an import would have."""
    parsed = yaml_util.parse_yaml(raw.format(source=source))
    item = Blueprint(parsed, schema=BLUEPRINT_SCHEMA)

    file = Path(hass.config.path("blueprints", domain, path))
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(item.yaml(), encoding="utf-8")
    return file


def write_by_hand(hass: HomeAssistant, domain: str, path: str, raw: str) -> Path:
    """Put a blueprint on disk exactly as written, without an import.

    Which is what a file looks like after somebody has edited it themselves,
    rather than one Home Assistant dumped back out.
    """
    file = Path(hass.config.path("blueprints", domain, path))
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(raw.format(source=SOURCE), encoding="utf-8")
    return file


def examples_are_on_disk(hass: HomeAssistant) -> bool:
    """Return whether Home Assistant laid its own example blueprints down."""
    return Path(
        hass.config.path("blueprints", "automation", "homeassistant"),
    ).is_dir()


def imported_from(raw: str, *, source: str = SOURCE) -> ImportedBlueprint:
    """Return what the importer would hand back for this blueprint."""
    body = raw.format(source=source)
    item = Blueprint(yaml_util.parse_yaml(body), schema=BLUEPRINT_SCHEMA)
    item.update_metadata(source_url=source)
    return ImportedBlueprint("spook/blueprint", body, item)


async def async_set_up(hass: HomeAssistant) -> ConfigEntry:
    """Set up automations, scripts and Spook's update platform."""
    assert await async_setup_component(hass, "automation", {"automation": []})
    assert await async_setup_component(hass, "script", {"script": {}})
    await hass.async_block_till_done()

    async def _setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.UPDATE])
        return True

    async def _unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        return await hass.config_entries.async_unload_platforms(
            entry,
            [Platform.UPDATE],
        )

    async def _setup_platform(
        hass: HomeAssistant,
        entry: ConfigEntry,
        add: AddConfigEntryEntitiesCallback,
    ) -> None:
        await async_set_up_updates(hass, entry, add)

    mock_integration(
        hass,
        MockModule(
            "fake",
            async_setup_entry=_setup_entry,
            async_unload_entry=_unload_entry,
        ),
    )
    mock_platform(hass, "fake.config_flow")
    mock_platform(hass, "fake.update", MockPlatform(async_setup_entry=_setup_platform))

    class _Flow(ConfigFlow, domain="fake"):
        """A config flow that does nothing."""

    with mock_config_flow("fake", _Flow):
        entry = MockConfigEntry(domain="fake")
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


def async_write_script_config(
    hass: HomeAssistant,
    scripts: dict[str, Any] | None = None,
) -> None:
    """Write the configuration.yaml a script reload will read back."""
    Path(hass.config.path("configuration.yaml")).write_text(
        yaml_util.dump({"automation": [], "script": scripts or {}}),
        encoding="utf-8",
    )


async def async_add_script(
    hass: HomeAssistant,
    key: str,
    path: str,
    inputs: dict[str, Any],
) -> None:
    """Add a script that runs on a blueprint, through a real reload."""
    async_write_script_config(
        hass,
        {key: {"use_blueprint": {"path": path, "input": inputs}}},
    )
    await hass.services.async_call("script", "reload", blocking=True)
    await hass.async_block_till_done()


async def async_add_automation(
    hass: HomeAssistant,
    alias: str,
    path: str,
    inputs: dict[str, Any],
) -> None:
    """Add an automation that runs on a blueprint, through a real reload."""
    async_write_config(
        hass,
        [
            {
                "id": alias.lower().replace(" ", "_"),
                "alias": alias,
                "use_blueprint": {"path": path, "input": inputs},
            },
        ],
    )
    await hass.services.async_call("automation", "reload", blocking=True)
    await hass.async_block_till_done()
