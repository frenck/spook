"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components import automation

from ....repairs import AbstractSpookRenamedEntityReferencesRepair


class SpookRepair(AbstractSpookRenamedEntityReferencesRepair):
    """Spook repair finds automations still pointing at a renamed entity.

    Unlike the repairs about turned-off automations staying quiet, this one
    looks at every automation: a rename just made the stored reference wrong
    whether the automation runs right now or not, and the moment the rename
    happened is exactly when the offer to fix it makes sense.
    """

    domain = automation.DOMAIN
    repair = "automation_renamed_entity_references"
    entity_label = "automation"
    edit_url_pattern = "/config/automation/edit/{unique_id}"
