"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.repairs import DOMAIN
from homeassistant.core import SupportsResponse
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.translation import async_get_translations

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall, ServiceResponse

_SEVERITIES = [severity.value for severity in ir.IssueSeverity]


class _KeepUnknownPlaceholders(dict[str, Any]):
    """Leave a placeholder that has no value as it was, rather than fail."""

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


def _title(translations: dict[str, str], issue: ir.IssueEntry) -> str:
    """Return the title of an issue the way the Repairs dashboard shows it.

    Home Assistant does not store the title, only where to find it and what
    to fill in. This looks it up the same way the frontend does, and falls
    back to the issue ID when there is nothing to look up.
    """
    key = issue.translation_key or issue.issue_id
    title = translations.get(f"component.{issue.domain}.issues.{key}.title")
    if title is None:
        return issue.issue_id

    try:
        return title.format_map(
            _KeepUnknownPlaceholders(issue.translation_placeholders or {})
        )
    except ValueError, IndexError:
        # Braces that are not a placeholder, like the plural forms some
        # translations use. Better the text as written than no title.
        return title


class SpookService(AbstractSpookAdminService):
    """Home Assistant Repairs service to list the open issues.

    For an automation to act on them, or a dashboard to show them, somewhere
    other than the Repairs page. An admin action, like core's own listing:
    the titles can say a fair bit about somebody's setup.
    """

    domain = DOMAIN
    service = "list"
    schema = {
        vol.Optional("include_ignored", default=False): cv.boolean,
        vol.Optional("domain"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("severity"): vol.All(cv.ensure_list, [vol.In(_SEVERITIES)]),
    }
    supports_response = SupportsResponse.ONLY

    async def async_handle_service(self, call: ServiceCall) -> ServiceResponse:
        """Handle the service call."""
        domains = set(call.data.get("domain", []))
        severities = set(call.data.get("severity", []))

        # An issue that is no longer raised can stay in the registry, to
        # remember it was ignored. The Repairs dashboard leaves those out.
        issues = [
            issue
            for issue in ir.async_get(self.hass).issues.values()
            if issue.active
            and (call.data["include_ignored"] or issue.dismissed_version is None)
            and (not domains or issue.domain in domains)
            and (not severities or issue.severity in severities)
        ]

        translations = await async_get_translations(
            self.hass,
            self.hass.config.language,
            "issues",
            {issue.domain for issue in issues},
        )

        issues.sort(key=lambda issue: issue.created, reverse=True)
        return {
            "issues": [
                {
                    "domain": issue.domain,
                    "issue_id": issue.issue_id,
                    "title": _title(translations, issue),
                    "severity": issue.severity,
                    "created": issue.created.isoformat(),
                    "is_fixable": issue.is_fixable,
                    "learn_more_url": issue.learn_more_url,
                    "breaks_in_ha_version": issue.breaks_in_ha_version,
                    "ignored": issue.dismissed_version is not None,
                }
                for issue in issues
            ]
        }
