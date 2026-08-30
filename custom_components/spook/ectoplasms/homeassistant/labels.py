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


# Kept in step with `homeassistant.components.config.label_registry`, which is
# what the label registry itself accepts. Copied rather than imported: reaching
# into a core component from here would break the day core moves it, and a
# copy that drifts is caught by the test that compares the two.
SUPPORTED_LABEL_THEME_COLORS = {
    "accent",
    "amber",
    "black",
    "blue",
    "blue-grey",
    "brown",
    "cyan",
    "dark-grey",
    "deep-orange",
    "deep-purple",
    "disabled",
    "green",
    "grey",
    "indigo",
    "light-blue",
    "light-green",
    "light-grey",
    "lime",
    "orange",
    "pink",
    "primary",
    "purple",
    "red",
    "teal",
    "white",
    "yellow",
}
