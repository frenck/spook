"""Spook - Your homie. Shared checks for the label actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import label_registry as lr

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant


@callback
def async_check_labels_exist(hass: HomeAssistant, label_ids: Iterable[str]) -> None:
    """Raise unless every one of these labels exists.

    Saying so beats doing nothing quietly: a typo in a label would otherwise
    come back as a successful call that changed nothing, and the automation
    that made it would carry on as though it had worked.
    """
    label_registry = lr.async_get(hass)

    for label_id in label_ids:
        if not label_registry.async_get_label(label_id):
            msg = f"Label {label_id} not found"
            raise HomeAssistantError(msg)
