"""Spook - Your homie. Shared rules for changing a group's members.

Home Assistant lost something when groups moved from YAML to helpers. The old
`group.set` could add and remove entities while the house was running, and it
still can, but only for the old kind of group. A group made through the
interface is a config entry, and nothing reaches into one of those from an
automation.

The three actions that put that back all do the same work apart from how they
arrive at the new list of members, so the work lives here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.group import DOMAIN as GROUP_DOMAIN
from homeassistant.components.group.const import CONF_HIDE_MEMBERS
from homeassistant.const import CONF_ENTITIES
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

# Which platform a group helper puts its entity on: `light`, `sensor`, and so
# on. Core writes and reads this key as a bare string with no constant of its
# own, so this is where Spook names it.
_GROUP_TYPE = "group_type"


def async_entry_of(hass: HomeAssistant, group_entity_id: str) -> ConfigEntry:
    """Return the config entry behind a group entity.

    Refuses anything that cannot be changed, and says which kind of "cannot"
    it is, because the three cases want three different things from whoever
    called. A group that came from YAML is the interesting one: it exists, it
    works, and editing it means editing the file it came from.
    """
    registry = er.async_get(hass)
    entry_entity = registry.async_get(group_entity_id)

    if entry_entity is None:
        # A group from YAML carries no unique ID, so it never reaches the
        # entity registry. Having a state is what separates one of those from
        # a name somebody mistyped.
        if hass.states.get(group_entity_id) is not None:
            msg = (
                f"{group_entity_id} is a group from your YAML configuration, "
                "which Spook cannot change. Edit it in your configuration, or "
                "use group.set, which still works on that kind of group."
            )
            raise HomeAssistantError(msg)

        msg = f"Could not find entity_id: {group_entity_id}"
        raise HomeAssistantError(msg)

    if entry_entity.platform != GROUP_DOMAIN:
        msg = f"{group_entity_id} is not a group"
        raise HomeAssistantError(msg)

    if (
        entry_entity.config_entry_id is None
        or (entry := hass.config_entries.async_get_entry(entry_entity.config_entry_id))
        is None
    ):
        msg = f"Could not find the group behind {group_entity_id}"
        raise HomeAssistantError(msg)

    return entry


def members_of(entry: ConfigEntry) -> list[str]:
    """Return the members a group currently has, in the order it holds them."""
    return list(entry.options.get(CONF_ENTITIES) or [])


def async_check_joining(
    hass: HomeAssistant,
    entry: ConfigEntry,
    members: list[str],
) -> None:
    """Refuse members a group cannot usefully hold.

    Both checks exist because Spook has a repair for the result of skipping
    them. A member from the wrong domain makes a group that reports nonsense,
    and a member that does not exist makes `group_unknown_members` fire on
    something Spook itself just did.

    Only asked about members that are joining. Taking one out is how somebody
    clears up exactly these mistakes, so removal never questions the name.
    """
    group_type = entry.options.get(_GROUP_TYPE)
    registry = er.async_get(hass)

    for member in members:
        # A group can hold a registry ID rather than an entity ID, and that
        # carries no domain of its own, so resolving comes first. Asking
        # `async_resolve_entity_id` whether something exists proves nothing:
        # it hands back anything already shaped like an entity ID.
        resolved = er.async_resolve_entity_id(registry, member)

        if resolved is None or (
            hass.states.get(resolved) is None and registry.async_get(resolved) is None
        ):
            msg = f"Could not find entity_id: {member}"
            raise HomeAssistantError(msg)

        if group_type and resolved.split(".")[0] != group_type:
            msg = f"{member} cannot join this group: it holds {group_type} entities"
            raise HomeAssistantError(msg)


async def async_write_members(
    hass: HomeAssistant,
    entry: ConfigEntry,
    members: list[str],
) -> None:
    """Give a group a new list of members, and make it take effect.

    Writing the options is not enough on its own. Nothing in the group
    integration listens for its own entry changing, so the group that is
    running keeps the list it was built from until something reloads it.
    """
    current = members_of(entry)
    if members == current:
        return

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_ENTITIES: members}
    )
    _async_follow_hiding(hass, entry, was=current, now=members)

    await hass.config_entries.async_reload(entry.entry_id)


@callback
def _async_follow_hiding(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    was: list[str],
    now: list[str],
) -> None:
    """Hide what joined and show what left, for a group that hides members.

    A group set to hide its members promises that what is in it is out of the
    way. Leaving that to the next reload would leave a member that just joined
    still on show, and one that just left hidden with nothing left to explain
    why.

    Only what this integration hid is shown again, the same rule core follows
    when a whole group is deleted. Somebody who hid an entity themselves meant
    it, and it is not this action's place to undo that.
    """
    if not entry.options.get(CONF_HIDE_MEMBERS):
        return

    registry = er.async_get(hass)

    for member in set(now) - set(was):
        if (entity_id := er.async_resolve_entity_id(registry, member)) and (
            registry.async_get(entity_id) is not None
        ):
            registry.async_update_entity(
                entity_id, hidden_by=er.RegistryEntryHider.INTEGRATION
            )

    for member in set(was) - set(now):
        if (entity_id := er.async_resolve_entity_id(registry, member)) is None or (
            entity := registry.async_get(entity_id)
        ) is None:
            continue

        if entity.hidden_by is er.RegistryEntryHider.INTEGRATION:
            registry.async_update_entity(entity_id, hidden_by=None)
