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
from homeassistant.components.group.config_flow import GroupConfigFlowHandler
from homeassistant.components.group.const import CONF_HIDE_MEMBERS
from homeassistant.const import CONF_ENTITIES
from homeassistant.core import callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, selector

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

# Which platform a group helper puts its entity on: `light`, `sensor`, and so
# on. Core writes and reads this key as a bare string with no constant of its
# own, so this is where Spook names it.
_GROUP_TYPE = "group_type"


def domains_a_group_holds(group_type: str) -> set[str] | None:
    """Return the domains core's own dialog offers for this kind of group.

    Read out of core rather than written down here, because it is not simply
    one domain per group: a sensor group takes `number` and `input_number`
    alongside `sensor`, and a copy of that here would be a copy that goes
    quietly out of date.

    Returns nothing when the shape of core's flow has moved, and then there
    is no domain check at all. That is the right way round to fail. Refusing
    a member the interface would have accepted is worse than storing an odd
    one, and there is a test that fails the moment this stops finding
    anything.
    """
    step = GroupConfigFlowHandler.config_flow.get(group_type)
    schema = getattr(step, "schema", None)
    if schema is None or not hasattr(schema, "schema"):
        return None

    for key, value in schema.schema.items():
        if str(key) == CONF_ENTITIES and isinstance(value, selector.EntitySelector):
            domains = value.config.get("domain")
            if isinstance(domains, str):
                return {domains}
            if domains:
                return set(domains)

    return None


def identity_of(hass: HomeAssistant, member: str) -> str:
    """Return what two references to the same entity have in common.

    A group is allowed to hold either an entity ID or a registry ID, and the
    interface writes whichever it has. Compared as plain strings, the two
    forms of one entity look like two entities: adding it a second time gets
    it stored twice, and asking for it to be taken out by the name it is not
    stored under reports success and changes nothing.

    A registry ID whose entry has gone resolves to nothing, and then the value
    itself is the best identity available. That keeps a dangling reference
    removable by exactly what is written in the group.
    """
    return er.async_resolve_entity_id(er.async_get(hass), member) or member


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
        if hass.states.get(group_entity_id) is None:
            msg = f"Could not find entity_id: {group_entity_id}"
            raise HomeAssistantError(msg)

        # Only the group domain holds that older kind. Anything else with a
        # state and no registry entry belongs to somebody else entirely, and
        # pointing them at `group.set` would send them a long way off.
        if split_entity_id(group_entity_id)[0] == GROUP_DOMAIN:
            msg = (
                f"{group_entity_id} is a group from your YAML configuration, "
                "which Spook cannot change. Edit it in your configuration, or "
                "use group.set, which still works on that kind of group."
            )
            raise HomeAssistantError(msg)

        msg = f"{group_entity_id} is not a group"
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
    allowed = domains_a_group_holds(group_type) if group_type else None
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

        if allowed is not None and split_entity_id(resolved)[0] not in allowed:
            msg = (
                f"{member} cannot join this group: it holds "
                f"{', '.join(sorted(allowed))} entities"
            )
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
    """Hide the members that just joined, for a group that hides its members.

    A group set to hide its members promises that what is in it is out of the
    way, and leaving that to the next reload would leave a member that just
    joined still on show.

    Nothing is ever shown again. That is not an omission, it is what the
    interface does: core applies the hiding to the new list of members and
    never touches one that left, so a member you take out through Settings
    stays hidden too. It is also the only safe answer, because `hidden_by`
    records that an integration hid something and never which one. Clearing
    it would mean guessing, and guessing wrong means undoing what another
    integration, or another group, still asks for.

    Only what is on show gets hidden. An entity somebody hid themselves, or
    that another integration is keeping out of the way, is already where the
    group wants it, so there is nothing to do and nothing to overwrite. Core
    is blunter here and writes over both.
    """
    if not entry.options.get(CONF_HIDE_MEMBERS):
        return

    registry = er.async_get(hass)

    # By identity rather than by the strings, or an entity stored as a
    # registry ID and named as an entity ID reads as a different member.
    before = {identity_of(hass, member) for member in was}

    for member in now:
        if (entity_id := identity_of(hass, member)) in before:
            continue

        entity = registry.async_get(entity_id)
        if entity is not None and entity.hidden_by is None:
            registry.async_update_entity(
                entity_id, hidden_by=er.RegistryEntryHider.INTEGRATION
            )
