"""Spook - Your homie."""

from __future__ import annotations

from ..entity_names import AbstractSpookDashboardAttributesRepair


class SpookRepair(AbstractSpookDashboardAttributesRepair):
    """Spook repair tries to find unknown attributes used in dashboards."""

    repair = "lovelace_unknown_attribute_references"
