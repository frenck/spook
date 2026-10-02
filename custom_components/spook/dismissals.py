"""Spook - Your homie. Remembering what somebody said to leave alone."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant

STORAGE_KEY = f"{DOMAIN}.dismissals"
STORAGE_VERSION = 1

# Not much rides on writing this the instant it changes, and pressing ignore
# on a handful of issues in a row is one write rather than a handful.
_SAVE_DELAY = 5

DATA_DISMISSALS: HassKey[Dismissals] = HassKey("spook_dismissals")


@dataclass(frozen=True)
class _Offered:
    """What an issue Spook raised was about."""

    repair: str
    owner: str
    references: frozenset[str]


class Dismissals:
    """The findings somebody ignored, per repair and per thing they were in.

    Home Assistant remembers that an issue was ignored, but it remembers it on
    the issue, and only for as long as that issue exists. Spook files an issue
    under its findings, so one finding more or less is a different issue, and
    an issue that goes for a moment is gone with its mark: an automation being
    reloaded, a dashboard that would not load, a restart before everything has
    arrived. Every one of those put an ignored finding back up as new. #1699,
    #1702.

    So the decision is written down here instead, where it outlasts the issue
    it was made on.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        store: Store[dict[str, dict[str, list[str]]]] | None = None,
        dismissed: dict[str, dict[str, list[str]]] | None = None,
    ) -> None:
        """Hold what was loaded."""
        self._hass = hass
        self._store = store
        self._dismissed: dict[str, dict[str, set[str]]] = {
            repair: {owner: set(references) for owner, references in owners.items()}
            for repair, owners in (dismissed or {}).items()
        }
        self._offered: dict[str, _Offered] = {}

    @callback
    def async_dismissed(self, repair: str, owner: str) -> set[str]:
        """Return what somebody ignored in this one, for this repair."""
        return set(self._dismissed.get(repair, {}).get(owner, ()))

    @callback
    def async_offer(
        self,
        issue_id: str,
        repair: str,
        owner: str,
        references: Iterable[str],
    ) -> None:
        """Remember what an issue is about, so ignoring it can be written down."""
        self._offered[issue_id] = _Offered(repair, owner, frozenset(references))

    @callback
    def async_dismiss_offered(self, issue_id: str) -> None:
        """Write down that the findings of this issue are to be left alone."""
        if (offered := self._offered.get(issue_id)) is None:
            return

        owners = self._dismissed.setdefault(offered.repair, {})
        dismissed = owners.setdefault(offered.owner, set())
        if offered.references <= dismissed:
            return

        dismissed |= offered.references
        self._async_schedule_save()

    @callback
    def async_undismiss_offered(self, issue_id: str) -> None:
        """Take back ignoring the findings of this issue."""
        if (offered := self._offered.get(issue_id)) is None:
            return

        owners = self._dismissed.get(offered.repair, {})
        if not (dismissed := owners.get(offered.owner)) or not (
            offered.references & dismissed
        ):
            return

        dismissed -= offered.references
        if not dismissed:
            del owners[offered.owner]
        self._async_schedule_save()

    @callback
    def async_issue_registry_updated(
        self,
        event: Event[ir.EventIssueRegistryUpdatedData],
    ) -> None:
        """Follow somebody ignoring an issue, or taking that back."""
        issue_id = event.data["issue_id"]
        if (
            event.data["action"] != "update"
            or event.data["domain"] != DOMAIN
            or issue_id not in self._offered
        ):
            return

        if (
            issue := ir.async_get(self._hass).async_get_issue(DOMAIN, issue_id)
        ) is None:
            return

        if issue.dismissed_version is not None:
            self.async_dismiss_offered(issue_id)
        else:
            self.async_undismiss_offered(issue_id)

    @callback
    def _async_schedule_save(self) -> None:
        """Write it down, soon."""
        if self._store is not None:
            self._store.async_delay_save(self._data_to_save, _SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, dict[str, list[str]]]:
        """Return what goes on disk."""
        return {
            repair: {owner: sorted(references) for owner, references in owners.items()}
            for repair, owners in self._dismissed.items()
            if owners
        }


@callback
def async_get_dismissals(hass: HomeAssistant) -> Dismissals:
    """Return the dismissals, or an empty set that is never written down.

    The empty set is for a repair asked to look without Spook having been set
    up around it, which is a test and not a house.
    """
    if (dismissals := hass.data.get(DATA_DISMISSALS)) is None:
        dismissals = hass.data[DATA_DISMISSALS] = Dismissals(hass)

    return dismissals


async def async_setup_dismissals(hass: HomeAssistant) -> CALLBACK_TYPE:
    """Load what was ignored before, and follow what gets ignored from now on.

    Before any repair looks, because the first thing a repair does with a
    finding is ask whether somebody already said to leave it alone.
    """
    store: Store[dict[str, dict[str, list[str]]]] = Store(
        hass, STORAGE_VERSION, STORAGE_KEY
    )
    dismissals = hass.data[DATA_DISMISSALS] = Dismissals(
        hass, store, await store.async_load()
    )

    unsubscribe = hass.bus.async_listen(
        ir.EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED,
        dismissals.async_issue_registry_updated,
    )

    @callback
    def _unload() -> None:
        """Stop following, and let go of what was loaded."""
        unsubscribe()
        hass.data.pop(DATA_DISMISSALS, None)

    return _unload
