"""Spook - Your homie."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.util import dt as dt_util

from ....const import LOGGER
from ....repairs import AbstractSpookRepair

# Long-lived access tokens do not expire on their own. One with no activity
# for this long is almost certainly forgotten. The window is generous so a
# token used by an infrequently-run script is not flagged.
_STALE_AFTER = timedelta(days=180)


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds long-lived access tokens that look forgotten.

    A long-lived access token never expires; one that has not been used in
    a long time is a standing credential worth reviewing. Each stale token
    gets its own fixable issue, so Spook can revoke it on request.
    """

    domain = "homeassistant"
    repair = "stale_access_tokens"
    # Staleness is driven by the passage of time, not by an event. Catch up
    # once Home Assistant has started, then re-check once a day.
    inspect_events = {EVENT_HOMEASSISTANT_STARTED}
    inspect_interval = timedelta(days=1)
    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        cutoff = dt_util.utcnow() - _STALE_AFTER
        for user in await self.hass.auth.async_get_users():
            if user.system_generated:
                continue
            for token in user.refresh_tokens.values():
                self.possible_issue_ids.add(token.id)
                if token.token_type != TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN:
                    continue
                last_activity = token.last_used_at or token.created_at
                if last_activity >= cutoff:
                    continue

                placeholders = {
                    "token": token.client_name or "Unnamed token",
                    "owner": user.name or "Unknown user",
                    "last_active": last_activity.date().isoformat(),
                }
                self.async_create_issue(
                    issue_id=token.id,
                    is_fixable=True,
                    data={"stale_access_token_id": token.id, **placeholders},
                    translation_placeholders=placeholders,
                )
