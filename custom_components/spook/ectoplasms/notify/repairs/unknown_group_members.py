"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.group.notify import GroupNotifyPlatform
from homeassistant.components.notify import DOMAIN
from homeassistant.components.notify.legacy import NOTIFY_SERVICES
from homeassistant.const import (
    CONF_ACTION,
    EVENT_COMPONENT_LOADED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
)

from ....const import LOGGER
from ....repairs import AbstractSpookRepair


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds notify groups with members that do not exist.

    A legacy notify group forwards a message to each action in its
    `services:` list. When one of those is renamed or its integration is
    removed, the group carries on delivering to the rest.

    Nothing reports it, either. The group fires all its members as tasks and
    awaits them with `asyncio.wait`, which does not re-raise, and nobody
    retrieves the results. So the missing action raises into a task that is
    never read, the group reports success, and one person quietly stops
    getting notified.
    """

    domain = DOMAIN
    repair = "notify_unknown_group_members"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_SERVICE_REGISTERED,
        EVENT_SERVICE_REMOVED,
    }
    inspect_on_reload = True
    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        for services in self.hass.data.get(NOTIFY_SERVICES, {}).values():
            for service in services:
                # Picked out by type rather than by the key they are stored
                # under, so a group set up through discovery is found too.
                if not isinstance(service, GroupNotifyPlatform):
                    continue

                # The name the group is called by: `notify.<name>`. Private,
                # but it is the only thing tying a notify service back to the
                # action it registered.
                # pylint: disable-next=protected-access
                name = service._service_name  # noqa: SLF001
                self.possible_issue_ids.add(name)

                # A member is a bare action slug, so `phone` in the
                # configuration means the `notify.phone` action.
                unknown = sorted(
                    member[CONF_ACTION]
                    for member in service.entities
                    if CONF_ACTION in member
                    and not self.hass.services.has_service(DOMAIN, member[CONF_ACTION])
                )
                if not unknown:
                    continue

                self.async_create_issue(
                    issue_id=name,
                    translation_placeholders={
                        "group": f"{DOMAIN}.{name}",
                        "members": "\n".join(
                            f"- `{DOMAIN}.{member}`" for member in unknown
                        ),
                    },
                )
                LOGGER.debug(
                    "Spook found notify group %s.%s using unknown members %s "
                    "and created an issue for it",
                    DOMAIN,
                    name,
                    ", ".join(unknown),
                )
