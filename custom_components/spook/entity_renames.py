"""Spook - Your homie. Tracking entity renames and repairing what they break.

Renaming an entity in the registry leaves stored references pointing at the
old entity ID. An automation or script written against `light.old` keeps
saying `light.old` after the entity became `light.new`, and breaks with no
warning anywhere. This module keeps a journal of the renames it sees, so
repairs can tell a *renamed* reference - something it can offer to rewrite -
apart from a merely unknown one, which it can only guess at.

The second half is the offer itself: rewriting the old entity ID into the
new one in `automations.yaml` or `scripts.yaml`, the files the editors
write, followed by a reload so the fix takes hold right away.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

from homeassistant.components import automation, script
from homeassistant.config import AUTOMATION_CONFIG_PATH, SCRIPT_CONFIG_PATH
from homeassistant.const import CONF_ID, SERVICE_RELOAD
from homeassistant.core import Event, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import DATA_INSTANCES
import homeassistant.helpers.entity_registry as er
from homeassistant.util.file import write_utf8_file_atomic
from homeassistant.util.yaml import dump, load_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# Where in hass.data the journal lives, and the marker saying the listener
# keeping it up is on.
DATA_ENTITY_RENAMES = "spook_entity_renames"
DATA_RENAME_TRACKING = "spook_entity_renames_tracking"


@callback
def async_get_entity_renames(hass: HomeAssistant) -> dict[str, str]:
    """Return the journal of renames seen this run: old entity ID to new.

    Only renames that happened while Spook was listening are in it. A restart
    empties it, which is fine: the repairs that read it say nothing then, and
    the unknown-reference repairs still report the broken reference, just
    without the one-click offer.
    """
    return hass.data.setdefault(DATA_ENTITY_RENAMES, {})  # type: ignore[return-value]


@callback
def async_track_entity_renames(hass: HomeAssistant) -> None:
    """Start journaling entity renames. Safe to call more than once.

    Registered by the rename repairs when they activate; the journal is
    shared, so whichever of them asks first puts the listener up.
    """
    if hass.data.get(DATA_RENAME_TRACKING):
        return
    hass.data[DATA_RENAME_TRACKING] = True
    journal = async_get_entity_renames(hass)

    @callback
    def _entity_registry_updated(
        event: Event[er.EventEntityRegistryUpdatedData],
    ) -> None:
        """Record a rename, and drop ids that resolve to something again.

        On an update carrying `old_entity_id` the journal is chained:
        anything that pointed at the old ID now points at the new one, so an
        issue raised for `a -> b` retargets itself when `b` becomes `c`. A
        rename back (`b` to `a` again) drops the `a` entry - references to
        `a` work once more - but keeps the `b -> a` one, since references to
        `b` are what is broken now.

        A *created* entity taking a journaled ID drops that entry too: the
        reference resolves again, this time to something the user put there
        on purpose, and rewriting it away would undo exactly that.
        """
        data = event.data
        if data["action"] == "create":
            journal.pop(data["entity_id"], None)
            return

        if data["action"] != "update" or not (
            old_entity_id := data.get("old_entity_id")
        ):
            return
        new_entity_id = data["entity_id"]

        for key, target in list(journal.items()):
            if target == old_entity_id:
                journal[key] = new_entity_id

        if journal.get(new_entity_id) == old_entity_id:
            # Renamed back to where it came from.
            del journal[new_entity_id]
        else:
            journal[old_entity_id] = new_entity_id

        # A chain that loops back onto itself means nothing is broken.
        for key, target in list(journal.items()):
            if key == target:
                del journal[key]

    hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _entity_registry_updated)


# Keys whose values are never entity references. An automation's own `id`
# must not be rewritten or the targeted reload no longer finds it, and a
# `device_id` naming the renamed entity's device is a different kind of
# reference the rewrite cannot fix anyway.
_ENTITY_ID_SKIP_KEYS = frozenset(
    {"id", "alias", "device_id", "area_id", "floor_id", "label_id", "event_type"}
)


def _entity_id_pattern(entity_id: str) -> re.Pattern[str]:
    """Return a pattern matching an entity ID as a standalone token."""
    return re.compile(rf"(?<!\w){re.escape(entity_id)}(?!\w)")


def entity_id_in_config(config: Any, entity_id: str) -> bool:
    """Return whether a config references an entity ID as a standalone token.

    Also matches references inside Jinja templates like states("old.id"),
    which `referenced_entities` does not extract.
    """
    pattern = _entity_id_pattern(entity_id)

    def _find(value: Any) -> bool:
        if isinstance(value, str):
            return bool(pattern.search(value))
        if isinstance(value, dict):
            return any(_find(key) or _find(item) for key, item in value.items())
        if isinstance(value, list):
            return any(_find(item) for item in value)
        return False

    return _find(config)


def replace_entity_id_in_config(
    config: Any, old_entity_id: str, new_entity_id: str
) -> tuple[Any, bool]:
    """Replace references to an entity ID inside an automation/script config.

    Returns a (possibly new) config object and whether anything was replaced.
    The entity ID is replaced wherever it occurs as a standalone token -
    structural entity_id values as well as references inside Jinja templates
    like states("old.id") or states.old.id.state.
    """
    pattern = _entity_id_pattern(old_entity_id)

    def _replace(value: Any) -> tuple[Any, bool]:
        if isinstance(value, str):
            new_value, count = pattern.subn(new_entity_id, value)
            return new_value, count > 0
        if isinstance(value, dict):
            changed = False
            new_dict = {}
            for key, item in value.items():
                new_key, key_changed = _replace(key)
                if key in _ENTITY_ID_SKIP_KEYS:
                    new_dict[new_key] = item
                else:
                    new_item, item_changed = _replace(item)
                    new_dict[new_key] = new_item
                    changed |= item_changed
                changed |= key_changed
            return new_dict, changed
        if isinstance(value, list):
            changed = False
            new_list = []
            for item in value:
                new_item, item_changed = _replace(item)
                new_list.append(new_item)
                changed |= item_changed
            return new_list, changed
        return value, False

    return _replace(config)


# YAML directives like !include or !env_var must not be expanded into the
# file, so a file carrying them is left alone entirely.
_YAML_DIRECTIVE = re.compile(r"!(include|env_var|secret)\b")

#: The file each domain's editor saves to.
_CONFIG_FILES: dict[str, str] = {
    automation.DOMAIN: AUTOMATION_CONFIG_PATH,
    script.DOMAIN: SCRIPT_CONFIG_PATH,
}

#: One lock per file, so a repair flow and the config editor cannot take a
#: read-modify-write cycle on the same file at the same time.
_config_write_locks: dict[str, asyncio.Lock] = {}


def _update_in_list(
    items: Any, config_id: str, old_entity_id: str, new_entity_id: str
) -> bool:
    """Rewrite the item keyed `id` in an automations.yaml list."""
    if not isinstance(items, list):
        return False
    for index, item in enumerate(items):
        if not isinstance(item, dict) or item.get(CONF_ID) != config_id:
            continue
        new_item, changed = replace_entity_id_in_config(
            item, old_entity_id, new_entity_id
        )
        if not changed:
            return False
        items[index] = new_item
        return True
    return False


def _update_in_mapping(
    items: Any, config_id: str, old_entity_id: str, new_entity_id: str
) -> bool:
    """Rewrite the entry keyed by object ID in a scripts.yaml mapping."""
    if not isinstance(items, dict) or config_id not in items:
        return False
    new_item, changed = replace_entity_id_in_config(
        items[config_id], old_entity_id, new_entity_id
    )
    if not changed:
        return False
    items[config_id] = new_item
    return True


def _update_entity_references(
    path: str, domain: str, config_id: str, old_entity_id: str, new_entity_id: str
) -> bool:
    """Replace references to a renamed entity in the stored config."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError:
        return False
    if _YAML_DIRECTIVE.search(raw):
        return False
    try:
        items = load_yaml(path)
    except HomeAssistantError, OSError:
        return False

    updated = (
        _update_in_list(items, config_id, old_entity_id, new_entity_id)
        if domain == automation.DOMAIN
        else _update_in_mapping(items, config_id, old_entity_id, new_entity_id)
    )
    if not updated:
        return False

    try:
        write_utf8_file_atomic(path, dump(items), private=True)
    except OSError:
        return False
    return True


async def async_update_entity_references(
    hass: HomeAssistant,
    domain: str,
    config_id: str,
    old_entity_id: str,
    new_entity_id: str,
) -> str:
    """Update references to a renamed entity in the stored config.

    Returns "updated", "cannot_update" when the file could not be rewritten
    (missing, unreadable, carrying YAML directives, or the config lives
    somewhere else, e.g. configuration.yaml), or "still_referenced" when the
    write and reload worked but the entity still points at the old ID -
    blueprint-driven references are not in the stored config.
    """
    path = hass.config.path(_CONFIG_FILES[domain])
    lock = _config_write_locks.setdefault(path, asyncio.Lock())

    async with lock:
        if not await hass.async_add_executor_job(
            _update_entity_references,
            path,
            domain,
            config_id,
            old_entity_id,
            new_entity_id,
        ):
            return "cannot_update"

        # Automation reload can target a single automation; script reload is
        # all or nothing.
        if domain == automation.DOMAIN:
            await hass.services.async_call(
                domain, SERVICE_RELOAD, {CONF_ID: config_id}, blocking=True
            )
        else:
            await hass.services.async_call(domain, SERVICE_RELOAD, blocking=True)

    component = hass.data.get(DATA_INSTANCES, {}).get(domain)
    entity = (
        next(
            (entity for entity in component.entities if entity.unique_id == config_id),
            None,
        )
        if component is not None
        else None
    )
    if entity is not None and (
        old_entity_id in getattr(entity, "referenced_entities", ())
        or (
            (raw_config := getattr(entity, "raw_config", None)) is not None
            and entity_id_in_config(raw_config, old_entity_id)
        )
    ):
        return "still_referenced"
    return "updated"
