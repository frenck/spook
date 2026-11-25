"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components import script

from ....repairs import AbstractSpookRenamedEntityReferencesRepair


class SpookRepair(AbstractSpookRenamedEntityReferencesRepair):
    """Spook repair finds scripts still pointing at a renamed entity."""

    domain = script.DOMAIN
    repair = "script_renamed_entity_references"
    entity_label = "script"
    edit_url_pattern = "/config/script/edit/{unique_id}"
