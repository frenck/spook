"""Spook - Your homie. Dashboards naming what their entities never have.

The attributes and states a dashboard reads or compares with, held against
what the automation repairs hold theirs against: `attribute_checking` and
`state_checking`, with the same evidence, so a dashboard and an automation
naming the same thing get the same answer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.lovelace import DOMAIN
from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_LOVELACE_UPDATED
from homeassistant.helpers import entity_registry as er

from ...attribute_checking import async_unknown_attributes
from ...const import LOGGER
from ...dashboard_names import (
    DashboardNames,
    Group,
    Pair,
    extract_names_from_dashboard_node,
    reported,
)
from ...repairs import AbstractSpookRepair
from ...state_checking import async_unknown_states
from .dashboards import async_dashboard_configs

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.components.lovelace.dashboard import (
        LovelaceStorage,
        LovelaceYAML,
    )
    from homeassistant.core import HomeAssistant

# What was meant, when Spook is near certain of it, keyed by what was named.
type Suggestions = dict[Pair, str | None]


async def async_unknown_dashboard_attributes(
    hass: HomeAssistant, pairs: Iterable[Pair]
) -> Suggestions:
    """Return the (entity ID, attribute) pairs whose entity never had it."""
    return {
        (finding.entity_id, finding.attribute): finding.suggestion
        for finding in await async_unknown_attributes(hass, pairs)
    }


async def async_unknown_dashboard_states(
    hass: HomeAssistant, pairs: Iterable[Pair]
) -> Suggestions:
    """Return the (entity ID, state) pairs whose entity is never in it."""
    return {
        (finding.entity_id, finding.state): finding.suggestion
        for finding in await async_unknown_states(hass, pairs)
    }


def finding_reference(pair: Pair) -> str:
    """Return how one finding is written down, the way the automations do."""
    entity_id, name = pair
    return f"{entity_id}:{name}"


class AbstractSpookDashboardEntityNamesRepair(AbstractSpookRepair, ABC):
    """Base for repairs about dashboards naming what an entity never has.

    Looks when the automation repairs about the same look: not right after a
    start, when the recorder has its hands full, and once a day for what
    changes with time alone. And whenever a dashboard is saved.

    Nothing goes into `possible_issue_ids`: an issue is keyed to its
    findings, and what this repair left behind is read back out of the
    registry instead.
    """

    domain = DOMAIN
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_LOVELACE_UPDATED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = True
    inspect_on_reload = True
    inspect_on_entity_added_or_removed = True
    automatically_clean_up_issues = True
    first_inspection_delay = timedelta(minutes=10)
    inspect_interval = timedelta(days=1)

    #: Translation placeholder holding the findings.
    reference_label: str
    #: How one finding reads in the issue, with `{name}` and `{entity_id}`.
    finding_line: str

    _dashboards: dict[str | None, LovelaceStorage | LovelaceYAML]

    @abstractmethod
    def _groups(self, names: DashboardNames) -> frozenset[Group]:
        """Return the groups of the kind this repair is about."""

    @abstractmethod
    async def _async_unknown(self, pairs: set[Pair]) -> Suggestions:
        """Return the pairs the entity never has, with what was meant."""

    async def async_activate(self) -> None:
        """Handle the activating a repair."""
        self._dashboards = self.hass.data["lovelace"].dashboards
        await super().async_activate()

    def _format_findings(self, findings: list[Pair], unknown: Suggestions) -> str:
        """Return the list of findings, each with its entity and best guess."""
        lines = []
        for entity_id, name in findings:
            line = self.finding_line.format(name=name, entity_id=entity_id)
            if (suggestion := unknown[entity_id, name]) is not None:
                line += f" (did you mean `{suggestion}`?)"
            lines.append(line)
        return "\n".join(lines)

    async def async_inspect(self) -> None:
        """Trigger an inspection.

        Every dashboard is read first and the entities asked about once, so
        the recorder hears one question per round rather than one per
        dashboard. Reported only for a dashboard that is still exactly the one
        that was read: one saved while the recorder was being asked may say
        something else entirely, and saving it starts the next round anyway.
        """
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        # Per dashboard, the config read and its groups by view, in view order.
        read: dict[str, tuple[dict[str, Any], list[tuple[int | str, Group]]]] = {}
        async for _dashboard, url_path, config in async_dashboard_configs(
            self._dashboards
        ):
            if config is None:
                continue
            read[url_path] = (config, self._groups_by_view(config))
            # Reading a dashboard is CPU-bound, and one can be big.
            await asyncio.sleep(0)

        unknown = await self._async_unknown(
            {
                pair
                for _config, groups in read.values()
                for _view_path, group in groups
                for pair in group
            }
        )

        async for dashboard, url_path, config in async_dashboard_configs(
            self._dashboards
        ):
            if url_path not in read or read[url_path][0] is not config:
                continue

            groups = read[url_path][1]
            if not (findings := reported((group for _, group in groups), unknown)):
                continue

            first_view_path = next(
                view_path for view_path, group in groups if group <= findings
            )
            title = "Overview"
            if dashboard.config:
                title = dashboard.config.get("title", url_path)

            sorted_findings = sorted(findings)
            self.async_create_issue(
                issue_id=url_path,
                references=[finding_reference(pair) for pair in sorted_findings],
                translation_placeholders={
                    self.reference_label: self._format_findings(
                        sorted_findings, unknown
                    ),
                    "dashboard": title,
                    "edit": f"/{url_path}/{first_view_path}?edit=1",
                },
            )
            LOGGER.debug(
                "Spook found unknown %s in dashboard %s and created an issue "
                "for it; %s: %s",
                self.reference_label,
                title,
                self.reference_label.capitalize(),
                ", ".join(finding_reference(pair) for pair in sorted_findings),
            )

    def _groups_by_view(self, config: dict[str, Any]) -> list[tuple[int | str, Group]]:
        """Return the groups a dashboard names, each with the view it is on.

        A dashboard run by a strategy stores no cards, only options for the
        cards it makes, so there is nothing to read in it.
        """
        if not isinstance(views := config.get("views"), list):
            return []

        groups: list[tuple[int | str, Group]] = []
        for view_index, view in enumerate(views):
            if not isinstance(view, dict):
                continue
            view_path: int | str = view.get("path") or view_index
            names = extract_names_from_dashboard_node(view)
            groups.extend((view_path, group) for group in self._groups(names))
        return groups


class AbstractSpookDashboardAttributesRepair(AbstractSpookDashboardEntityNamesRepair):
    """Base for the repair about attributes an entity never had."""

    reference_label = "attributes"
    finding_line = "- `{name}` of `{entity_id}`"

    def _groups(self, names: DashboardNames) -> frozenset[Group]:
        """Return the attribute groups."""
        return names.attributes

    async def _async_unknown(self, pairs: set[Pair]) -> Suggestions:
        """Return the (entity ID, attribute) pairs the entity never had."""
        return await async_unknown_dashboard_attributes(self.hass, pairs)


class AbstractSpookDashboardStatesRepair(AbstractSpookDashboardEntityNamesRepair):
    """Base for the repair about states an entity is never in."""

    reference_label = "states"
    finding_line = "- `{name}` for `{entity_id}`"

    def _groups(self, names: DashboardNames) -> frozenset[Group]:
        """Return the state groups."""
        return names.states

    async def _async_unknown(self, pairs: set[Pair]) -> Suggestions:
        """Return the (entity ID, state) pairs the entity is never in."""
        return await async_unknown_dashboard_states(self.hass, pairs)


async def async_check_dashboard_draft(
    hass: HomeAssistant, node: Any
) -> dict[str, list[str]]:
    """Return the attributes and states a draft names that are unknown.

    Written the way the automation draft check writes them: the entity, the
    name, and what was most likely meant.
    """
    names = extract_names_from_dashboard_node(node)
    checks = {
        "attributes": (names.attributes, async_unknown_dashboard_attributes),
        "states": (names.states, async_unknown_dashboard_states),
    }

    found: dict[str, list[str]] = {}
    for label, (groups, async_unknown) in checks.items():
        pairs = {pair for group in groups for pair in group}
        unknown = await async_unknown(hass, pairs) if pairs else {}
        lines = []
        for pair in reported(groups, unknown):
            line = finding_reference(pair)
            if (suggestion := unknown[pair]) is not None:
                line += f" (did you mean {suggestion}?)"
            lines.append(line)
        if lines:
            found[label] = sorted(lines)
    return found
