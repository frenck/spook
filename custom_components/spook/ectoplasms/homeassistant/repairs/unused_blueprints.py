"""Spook - Your homie."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.components import blueprint
from homeassistant.components.automation import automations_with_blueprint
from homeassistant.components.script import scripts_with_blueprint
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.util import dt as dt_util

from ....const import LOGGER
from ....repairs import AbstractSpookRepair

if TYPE_CHECKING:
    from pathlib import Path

# Give a freshly added or edited blueprint time to be put to use before
# nagging about it. Judged by the blueprint file's modification time.
_MINIMUM_AGE = timedelta(days=1)


def _file_mtime(path: Path) -> float | None:
    """Return the file's modification time, or None if it cannot be read."""
    try:
        return path.stat().st_mtime
    except OSError:
        return None


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds blueprints that no automation or script uses.

    Blueprints pile up after you try one out and move on. A blueprint with
    zero consumers is dead weight. Surfaced as tidiness, with a fix flow to
    remove it. A blueprint whose file was added or changed within the grace
    period is left alone, so importing one to use in a moment does not
    trigger an instant repair.
    """

    domain = "homeassistant"
    repair = "unused_blueprints"
    inspect_events = {EVENT_HOMEASSISTANT_STARTED}
    inspect_on_reload = True
    inspect_interval = timedelta(days=1)
    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger an inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        domain_blueprints: dict[str, blueprint.DomainBlueprints] = self.hass.data.get(
            blueprint.DOMAIN, {}
        )
        cutoff = (dt_util.utcnow() - _MINIMUM_AGE).timestamp()
        for domain, domain_blueprint in domain_blueprints.items():
            # Only automations and scripts consume blueprints. A domain Spook
            # cannot check is skipped, so it never guesses a blueprint unused.
            if domain == "automation":
                consumers = automations_with_blueprint
            elif domain == "script":
                consumers = scripts_with_blueprint
            else:
                continue

            for path, item in (await domain_blueprint.async_get_blueprints()).items():
                issue_id = f"{domain}:{path}"
                self.possible_issue_ids.add(issue_id)

                if not isinstance(item, blueprint.Blueprint):
                    # Failed to load or missing; not a usage question.
                    continue
                if consumers(self.hass, path):
                    continue

                mtime = await self.hass.async_add_executor_job(
                    _file_mtime, domain_blueprint.blueprint_folder / path
                )
                if mtime is None or mtime > cutoff:
                    # File gone, or added/changed recently; give it time.
                    continue

                self.async_create_issue(
                    issue_id=issue_id,
                    is_fixable=True,
                    data={
                        "unused_blueprint_domain": domain,
                        "unused_blueprint_path": path,
                        "blueprint": item.name,
                    },
                    translation_placeholders={
                        "blueprint": item.name,
                        "domain": domain,
                    },
                )
