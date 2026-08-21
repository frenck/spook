"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components.alert.const import DOMAIN
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
)

from ....const import LOGGER
from ....repairs import AbstractSpookRepair
from ..configuration import async_get_alert_configurations


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds alerts notifying through actions that do not exist.

    An alert sends its notifications through legacy notify actions, named in
    its `notifiers:` list. When one of those is renamed or its integration is
    removed, the alert still fires and still does its rounds, but that
    notification goes nowhere.

    Home Assistant logs an error when it happens, except that only happens
    the moment the alert fires. An alert can sit quiet for months, which is
    the whole point of having one, and by the time it finally has something
    to say is a poor moment to find out nobody is listening.
    """

    domain = DOMAIN
    repair = "alert_unknown_notifiers"
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

        for alert in await async_get_alert_configurations(self.hass):
            self.possible_issue_ids.add(alert.entity_id)

            # A notifier is the name of a legacy notify action, so `my_phone`
            # in the configuration means the `notify.my_phone` action.
            unknown = sorted(
                notifier
                for notifier in alert.notifiers
                if not self.hass.services.has_service(NOTIFY_DOMAIN, notifier)
            )
            if not unknown:
                continue

            self.async_create_issue(
                issue_id=alert.entity_id,
                translation_placeholders={
                    "alert": alert.name,
                    "entity_id": alert.entity_id,
                    "notifiers": "\n".join(
                        f"- `{NOTIFY_DOMAIN}.{notifier}`" for notifier in unknown
                    ),
                },
            )
            LOGGER.debug(
                "Spook found alert %s using unknown notifiers %s "
                "and created an issue for it",
                alert.entity_id,
                ", ".join(unknown),
            )
