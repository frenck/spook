"""Spook - Your homie."""

from __future__ import annotations

from ..entity_names import AbstractSpookDashboardStatesRepair


class SpookRepair(AbstractSpookDashboardStatesRepair):
    """Spook repair tries to find unknown states used in dashboards."""

    repair = "lovelace_unknown_state_references"
