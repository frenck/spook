"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.helpers import config_validation as cv, issue_registry as ir

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant

CONF_DOMAIN = "domain"
CONF_SEVERITY = "severity"

SEVERITIES = tuple(severity.value for severity in ir.IssueSeverity)

# Optional filters, shared by the repair triggers and the condition so they
# read the same in the automation editor and in YAML.
FILTER_SCHEMA = {
    vol.Optional(CONF_DOMAIN): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_SEVERITY): vol.All(cv.ensure_list, [vol.In(SEVERITIES)]),
}

DOMAIN_ONLY_FILTER_SCHEMA = {
    vol.Optional(CONF_DOMAIN): vol.All(cv.ensure_list, [cv.string]),
}


def as_filter(options: dict[str, Any]) -> tuple[set[str] | None, set[str] | None]:
    """Turn the options into the two sets that do the filtering.

    ``None`` means "no opinion", which is not the same as an empty set: a
    filter nobody set has to let everything through.
    """
    domains = options.get(CONF_DOMAIN)
    severities = options.get(CONF_SEVERITY)
    return (
        set(cv.ensure_list(domains)) if domains else None,
        set(cv.ensure_list(severities)) if severities else None,
    )


def matches(
    issue: ir.IssueEntry,
    domains: set[str] | None,
    severities: set[str] | None,
) -> bool:
    """Return whether this issue is one that was asked about."""
    if domains is not None and issue.domain not in domains:
        return False

    if severities is None:
        return True

    # An issue is allowed to carry no severity at all, and then it cannot
    # answer a question about severity.
    return issue.severity is not None and issue.severity.value in severities


def is_ignored(issue: ir.IssueEntry) -> bool:
    """Return whether somebody told Home Assistant to stop nagging about this.

    Ignoring an issue does not deactivate it or take it out of the registry,
    it stamps the version it was ignored in, so that is what has to be read.
    """
    return issue.dismissed_version is not None


def active_issues(hass: HomeAssistant) -> Iterable[ir.IssueEntry]:
    """Yield the issues worth counting: present, active, and not ignored."""
    for issue in ir.async_get(hass).issues.values():
        if issue.active and not is_ignored(issue):
            yield issue


def payload(issue: ir.IssueEntry) -> dict[str, Any]:
    """Describe an issue for the trigger variables."""
    return {
        "domain": issue.domain,
        "issue_id": issue.issue_id,
        "severity": issue.severity.value if issue.severity else None,
        "is_fixable": issue.is_fixable,
        "breaks_in_ha_version": issue.breaks_in_ha_version,
        "learn_more_url": issue.learn_more_url,
        "translation_key": issue.translation_key,
    }
