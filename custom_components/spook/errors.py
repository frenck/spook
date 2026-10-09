"""Spook - Your homie. The errors Spook's actions raise most.

Each one is translated, so people read it in their own language in the
frontend, and the same error reads the same everywhere Spook raises it.
"""

from __future__ import annotations

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


def area_not_found(area_id: str) -> HomeAssistantError:
    """Return the error for an area that does not exist."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="area_not_found",
        translation_placeholders={"area_id": area_id},
    )


def config_entry_not_found(config_entry_id: str) -> HomeAssistantError:
    """Return the error for an integration entry that does not exist."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="config_entry_not_found",
        translation_placeholders={"config_entry_id": config_entry_id},
    )


def device_not_found(device_id: str) -> HomeAssistantError:
    """Return the error for a device that does not exist."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="device_not_found",
        translation_placeholders={"device_id": device_id},
    )


def entity_not_found(entity_id: str) -> HomeAssistantError:
    """Return the error for an entity that does not exist."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="entity_not_found",
        translation_placeholders={"entity_id": entity_id},
    )


def floor_not_found(floor_id: str) -> HomeAssistantError:
    """Return the error for a floor that does not exist."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="floor_not_found",
        translation_placeholders={"floor_id": floor_id},
    )


def label_not_found(label_id: str) -> HomeAssistantError:
    """Return the error for a label that does not exist."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="label_not_found",
        translation_placeholders={"label_id": label_id},
    )


def user_not_found(user_id: str) -> HomeAssistantError:
    """Return the error for a user that does not exist."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="user_not_found",
        translation_placeholders={"user_id": user_id},
    )
